#!/bin/bash

# Ejemplo de deployment automatizado del GitLab Runner
# Este script muestra cómo usar el nuevo sistema automatizado

set -e

echo "🚀 GitLab Runner Automated Deployment"
echo "======================================"

# Verificar que GitLab está desplegado primero
echo "📋 Verificando prerrequisitos..."

# Verificar si GitLab está desplegado
if ! kubectl get namespace gitlab >/dev/null 2>&1; then
    echo "❌ GitLab namespace no encontrado"
    echo "💡 Desplegando GitLab primero..."
    ansible-playbook -i inventories/service-cluster-lab/hosts.ini Step02-deploy.yml --tags gitlab --ask-vault-pass
fi

# Verificar estado de GitLab
echo "🔍 Verificando estado de GitLab..."
kubectl get pods -n gitlab
kubectl get svc -n gitlab

# Desplegar GitLab Runner con token automático
echo "🏃 Desplegando GitLab Runner con obtención automática de token..."
ansible-playbook -i inventories/service-cluster-lab/hosts.ini Step02-deploy.yml --tags gitlab-runner --ask-vault-pass -v

# Verificar deployment
echo "✅ Verificando deployment del GitLab Runner..."
kubectl get pods -n gitlab-runner
kubectl get svc -n gitlab-runner

echo "🎉 ¡Deployment completado!"
echo ""
echo "📊 Para verificar que el runner se registró correctamente:"
echo "   1. Ve a GitLab UI: https://gitlab.cicd.example.test/admin/runners"
echo "   2. O ejecuta: kubectl logs -n gitlab-runner deployment/gitlab-runner"
echo ""
echo "🔧 Para troubleshooting:"
echo "   kubectl describe pods -n gitlab-runner"
echo "   kubectl logs -n gitlab-runner deployment/gitlab-runner -f"