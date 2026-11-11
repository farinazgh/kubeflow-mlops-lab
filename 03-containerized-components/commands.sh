
#!/usr/bin/env bash
set -euo pipefail

cd /home/ubuntu/kubeflow-mlops-lab

KFP_VERSION=2.18.0
KFP_NAMESPACE=kubeflow
NODE=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')


# 1. NAMESPACE
# Isolate Kubeflow workloads from the existing cluster components.
# Namespace creation is idempotent.

kubectl create namespace "$KFP_NAMESPACE" \
  --dry-run=client -o yaml | kubectl apply -f -


# 2. CLUSTER RESOURCE ASSESSMENT
# Review available node capacity before introducing KFP workloads.

kubectl describe node | sed -n '/Allocated resources:/,/Events:/p'


# 3. LOCAL STORAGE
# Prepare two directories on the EC2 filesystem for persistent data.
# MySQL stores pipeline metadata; SeaweedFS stores pipeline artifacts.

mkdir -p /var/lib/kfp/{mysql,seaweedfs}

chown 999:999 /var/lib/kfp/mysql
chown 1000:1000 /var/lib/kfp/seaweedfs


# 4. KUBERNETES STORAGE OBJECTS
# Create a StorageClass and two statically provisioned local PVs.
# StorageClass and PersistentVolume are cluster-scoped objects.

mkdir -p manifests/kfp-standalone

cat > manifests/kfp-local-storage.yaml <<EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: kfp-local
provisioner: kubernetes.io/no-provisioner
volumeBindingMode: WaitForFirstConsumer
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: kfp-mysql-pv
spec:
  capacity:
    storage: 5Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: kfp-local
  local:
    path: /var/lib/kfp/mysql
  nodeAffinity:
    required:
      nodeSelectorTerms:
        - matchExpressions:
            - key: kubernetes.io/hostname
              operator: In
              values:
                - "$NODE"
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: kfp-seaweedfs-pv
spec:
  capacity:
    storage: 5Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: kfp-local
  local:
    path: /var/lib/kfp/seaweedfs
  nodeAffinity:
    required:
      nodeSelectorTerms:
        - matchExpressions:
            - key: kubernetes.io/hostname
              operator: In
              values:
                - "$NODE"
EOF

kubectl apply -f manifests/kfp-local-storage.yaml


# 5. RENDER CUSTOMIZED KUBEFLOW MANIFESTS
# Use our existing Kustomize overlay, which specifies:
# - namespace: kubeflow
# - KFP version 2.18.0
# - StorageClass: kfp-local
# - PVC requests: 5Gi each
# Rendering does not deploy the KFP workloads.

kubectl kustomize manifests/kfp-standalone \
  > /tmp/kfp-custom.yaml


# 6. VALIDATION
# Confirm namespace, PVs, StorageClass, and PVC definitions.

kubectl get namespace "$KFP_NAMESPACE"
kubectl get storageclass,pv

grep -A 16 '^kind: PersistentVolumeClaim' \
  /tmp/kfp-custom.yaml

echo "Kubeflow infrastructure preparation completed."
