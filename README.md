# Heartbound: Romance Reading Tracker

A Flask web app to track romance books you want to read, are reading, and have finished,
with 1-5 heart ratings, short reviews and a yearly reading goal.

CI/CD: `git push -> GitHub -> Jenkins -> tests -> Docker build/push -> Kubernetes deploy`

## Run locally
    pip install -r requirements.txt
    python app.py            # http://localhost:5000

## Test
    python -m pytest -v

## Docker
    docker build -t book-tracker .
    docker run -d -p 5000:5000 book-tracker

## Kubernetes (Minikube)
    kubectl apply -f k8s/
    minikube service book-service
