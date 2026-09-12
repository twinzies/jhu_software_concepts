"""Runs app.py's standardizer over every applicant row in parallel.

Only the unique program strings are sent to the model, and each result is cached on disk - an interrupted run resumes instead of starting over.
"""
import argparse
import json
import multiprocessing
import os
from pathlib import Path

HERE = Path(__file__).parent

def _standardize(program):
    """Standardizes one program string in a worker process."""
    # Imported here so each worker loads its own model, lazily, on first use.
    from app import _call_llm

    result = _call_llm(program)
    return program, result["standardized_program"], result["standardized_university"]

def _load_cache(cache_path):
    """Reads the programs standardized by earlier runs."""
    cache = {}
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as cache_file:
            for line in cache_file:
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue  # Skip a line left half-written by an interrupted run.

                cache[entry["program"]] = entry
    return cache

def _standardize_programs(programs, cache_path, workers, limit):
    """Standardizes every program not already cached, appending results as they arrive."""
    cache = _load_cache(cache_path)
    todo = [program for program in programs if program not in cache]
    if limit:
        todo = todo[:limit]

    print(f"{len(programs)} unique programs, {len(cache)} cached, {len(todo)} to standardize")

    with open(cache_path, "a", encoding="utf-8") as cache_file, \
            multiprocessing.Pool(workers) as pool:
        results = pool.imap_unordered(_standardize, todo, chunksize=4)

        for done, (program, std_program, std_university) in enumerate(results, start=1):
            entry = {"program": program,
                     "llm-generated-program": std_program,
                     "llm-generated-university": std_university}
            cache[program] = entry

            # Flushed per result so stopping the run never loses finished work.
            cache_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            cache_file.flush()

            if done % 50 == 0 or done == len(todo):
                print(f"  {done}/{len(todo)}", flush=True)

    return cache

def main():
    """Standardizes the cleaned applicant file and writes the extended copy."""
    cores = os.cpu_count() or 2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=str(HERE.parent / "applicant_data.json"))
    parser.add_argument("--out", default=str(HERE.parent / "llm_extend_applicant_data.json"))
    parser.add_argument("--cache", default=str(HERE / "llm_cache.jsonl"))
    parser.add_argument("--workers", type=int, default=max(1, cores // 2))
    parser.add_argument("--limit", type=int, default=0, help="Standardize at most N programs.")
    args = parser.parse_args()

    input_path, output_path = Path(args.file).resolve(), Path(args.out).resolve()
    cache_path = Path(args.cache).resolve()

    # Share the cores between workers, then run where app.py's canonical lists live.
    os.environ.setdefault("N_THREADS", str(max(1, cores // args.workers)))
    os.chdir(HERE)

    with open(input_path, encoding="utf-8") as input_file:
        rows = json.load(input_file)

    programs = sorted({row["program"] or "" for row in rows})
    cache = _standardize_programs(programs, cache_path, args.workers, args.limit)

    missing = [program for program in programs if program not in cache]
    if missing:
        print(f"{len(missing)} programs still to standardize; rerun to continue.")
        return

    for row in rows:
        entry = cache[row["program"] or ""]
        row["llm-generated-program"] = entry["llm-generated-program"]
        row["llm-generated-university"] = entry["llm-generated-university"]

    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(rows, output_file, ensure_ascii=False, indent=2)

    print(f"Wrote {len(rows)} rows to {output_path.name}")


if __name__ == "__main__":
    main()
