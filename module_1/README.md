# Module 1: Personal Website

## Project Description

A personal developer website built with Flask. It has three pages - a homepage with a biography and photo, a projects page, and a contact page — sharing a navigation bar.

## Quick Start Guide

From the `module_1` folder:

```bash
python -m venv .venv
source .venv/bin/activate 
pip install -r requirements.txt
python run.py
```

Then open <http://localhost:8080>.

Requires Python 3.10 or higher.

## Module repository structure

```
module_1/
├── run.py      # entry point;
├── requirements.txt
├── README.md    # this file
├── README.txt   # Assignment reqd.
└── app/
    ├── __init__.py 
    ├── routes.py  # "main" blueprint
    ├── templates/
    │   ├── base.html   # shared nav-bar
    │   ├── home.html
    │   ├── projects.html
    │   └── contact.html
    └── static/
        ├── css/style.css
        └── img/profile.png
```
## Project Status

[Completed]
