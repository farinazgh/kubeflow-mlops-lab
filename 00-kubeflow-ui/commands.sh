# Headlamp is a Kubernetes dashboard UI.
# We need it because we want a browser-based way to inspect pods, services, deployments, and logs without using only kubectl.
helm repo add headlamp https://kubernetes-sigs.github.io/headlamp/

helm repo update

helm upgrade --install headlamp headlamp/headlamp --namespace headlamp --create-namespace

# These checks verify that Headlamp is healthy and ready.
# waits for the rollout to finish
kubectl rollout status deployment/headlamp -n headlamp
kubectl get pods,svc -n headlamp

#  dashboard needs to inspect cluster data without having full admin rights.
kubectl -n headlamp create serviceaccount headlamp-viewer

# The clusterrolebinding connects the service account to the built-in view role.
kubectl create clusterrolebinding headlamp-viewer --clusterrole=view --serviceaccount=headlamp:headlamp-viewer

kubectl -n headlamp create token headlamp-viewer --duration=1h

kubectl -n headlamp port-forward svc/headlamp 8081:80

# This is an SSH tunnel through the EC2 instance.
# We need it when the cluster is running on a remote VM and we want a secure path to the forwarded service.
# It forwards the local port on your machine through the VM to the cluster-side port.
ssh -i "moomin-mamma.pem" -L 8080:127.0.0.1:8080 ubuntu@ec2-52-214-87-145.eu-west-1.compute.amazonaws.com
# This is the Kubeflow Pipelines UI.
# We need it because Kubeflow has its own web interface for running and monitoring ML pipelines.
# This command exposes the ml-pipeline-ui service locally on port 8080.
kubectl -n kubeflow port-forward svc/ml-pipeline-ui 8080:80
