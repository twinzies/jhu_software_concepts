"""Entry point for the personal website.Can be run with python run.py."""

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Make the site reachable as localhost:8080.
    app.run(host="0.0.0.0", port=8080, debug=True)
