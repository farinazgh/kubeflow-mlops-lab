sudo -n kubectl -n headlamp create token headlamp-viewer --duration=3h

kubectl -n headlamp port-forward svc/headlamp 8081:80

ssh -i "moomin-mamma.pem" -L 8081:localhost:8081 ubuntu@ec2-52-214-87-145.eu-west-1.compute.amazonaws.com