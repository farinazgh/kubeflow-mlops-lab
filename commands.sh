# Available resources: check host memory, disk usage, and cluster node resource consumption
free -h
df -h / 
kubectl top nodes 
 
# Storage: inspect persistent volumes, claims, and CSI drivers for cluster storage health* 
kubectl get pv 
kubectl get pvc -A 
kubectl get csidrivers 
 
# Kubernetes node taints: review node scheduling constraints and allocatable resources* 
kubectl describe node | grep -E 'Taints:|Allocatable:' -A 7 
 
helm version --short"