pipeline {
    agent any

    triggers {
        // Check GitHub every minute so every push starts a build automatically
        pollSCM('* * * * *')
    }

    environment {
        DOCKER_USER = 'sneha234567'
        IMAGE       = "${DOCKER_USER}/book-tracker"
        TAG         = "${env.BUILD_NUMBER}"
        KUBECONFIG  = 'C:\\Users\\sneha\\.kube\\config'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install & Test') {
            steps {
                bat '''
                    "C:\\Users\\sneha\\AppData\\Local\\Programs\\Python\\Python312\\python.exe" -m venv venv
                    venv\\Scripts\\pip install -r requirements.txt
                    venv\\Scripts\\python -m pytest -v
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                bat 'docker build -t %IMAGE%:%TAG% -t %IMAGE%:latest .'
            }
        }

        stage('Push to Docker Hub') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                        usernameVariable: 'USER', passwordVariable: 'PASS')]) {
                    bat '''
                        echo %PASS%| docker login -u %USER% --password-stdin
                        docker push %IMAGE%:%TAG%
                        docker push %IMAGE%:latest
                    '''
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                bat '''
                    powershell -Command "(Get-Content k8s/deployment.yaml) -replace 'IMAGE_PLACEHOLDER', '%IMAGE%:%TAG%' | Set-Content k8s/deployment.yaml"
                    kubectl apply -f k8s/deployment.yaml
                    kubectl apply -f k8s/service.yaml
kubectl rollout status deployment/book-tracker --timeout=300s                '''
            }
        }
    }

    post {
        success { echo 'Pipeline finished: Heartbound deployed to Kubernetes.' }
        failure { echo 'Pipeline failed. Check the stage logs above.' }
    }
}
