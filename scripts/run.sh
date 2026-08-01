#!/bin/bash

# Ensure there are ni additonal proccesses running 
lsof -ti :5500 | xargs kill

uvicorn src.app:app --reload &
BACKEND_PID=$!

python3 -m http.server 5500 --directory frontend &
FRONTEND_PID=$!

sleep 1

open -a Safari "http://127.0.0.1:5500/"

wait