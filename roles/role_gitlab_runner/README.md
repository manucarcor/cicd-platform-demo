# GitLab Runner Role - Automated Token Retrieval

Este rol del GitLab Runner ha sido mejorado para obtener automáticamente el token de registro desde la instancia de GitLab desplegada, eliminando la necesidad de configuración manual.

## 🔄 Flujo Automatizado

### 1. Verificación de GitLab
- ✅ Verifica que el namespace de GitLab existe
- ✅ Verifica que el StatefulSet de GitLab está desplegado
- ✅ Espera a que GitLab esté completamente listo (pod y servicios)
- ✅ Verifica conectividad web y API

### 2. Obtención Automática del Token
El rol utiliza múltiples métodos de fallback para obtener el token:

#### Método Principal
```bash
gitlab-rails runner "puts Gitlab::CurrentSettings.runners_registration_token"
```

#### Método de Fallback 1 (API)
- Crea un token temporal de API para el usuario root
- Obtiene el token via `/api/v4/admin/runners`
- Limpia el token temporal automáticamente

#### Método de Fallback 2 (Database Direct)
- Acceso directo a ApplicationSettings
- Genera un nuevo token si no existe
- Guarda la configuración en la base de datos

### 3. Deployment del GitLab Runner
- Usa el token obtenido dinámicamente
- Continúa con el deployment normal del Helm chart

## 🚀 Uso

### Deployment Completo
```bash
# Desplegar todo (incluyendo GitLab y luego GitLab Runner)
ansible-playbook -i inventories/service-cluster-lab/hosts.ini Step02-deploy.yml --ask-vault-pass
```

### Solo GitLab Runner (GitLab ya desplegado)
```bash
# Solo desplegar GitLab Runner
ansible-playbook -i inventories/service-cluster-lab/hosts.ini Step02-deploy.yml --tags gitlab-runner --ask-vault-pass
```

## 🔧 Variables Requeridas

Las siguientes variables deben estar configuradas en tu inventario:

```yaml
# GitLab Configuration (debe estar desplegado primero)
gitlab_namespace: "gitlab"
gitlab_app_name: "gitlab"
gitlab_url: "https://gitlab.cicd.example.test"

# GitLab Runner Configuration
gitlab_runner_namespace: "gitlab-runner"
gitlab_runner_app_name: "gitlab-runner"
# ... otras variables del runner
```

## 🛠️ Troubleshooting

### GitLab no está listo
```bash
# Verificar estado de GitLab
kubectl get pods -n gitlab
kubectl logs -n gitlab gitlab-0

# Verificar conectividad
curl -k https://gitlab.cicd.example.test/api/v4/version
```

### Token no se puede obtener
```bash
# Obtener token manualmente
kubectl exec -n gitlab gitlab-0 -- gitlab-rails runner "puts Gitlab::CurrentSettings.runners_registration_token"

# Verificar permisos del pod
kubectl exec -n gitlab gitlab-0 -- gitlab-rails runner "puts User.find_by(username: 'root')&.admin?"
```

### Fallo en el deployment del Runner
```bash
# Verificar logs del deployment
kubectl logs -n gitlab-runner deployment/gitlab-runner

# Verificar configuración
kubectl get configmap -n gitlab-runner
kubectl describe configmap -n gitlab-runner gitlab-runner-config
```

## 📋 Logs y Debugging

El rol proporciona información detallada durante la ejecución:

```
✅ GitLab is ready! Version: 16.x.x, Revision: xxxxx
✅ GitLab registration token obtained successfully: glrt-xxx***
✅ Token retrieval successful!
```

### Habilitar Modo Verbose
```bash
ansible-playbook -vvv -i inventories/service-cluster-lab/hosts.ini Step02-deploy.yml --tags gitlab-runner
```

## 🔒 Seguridad

- Los tokens se muestran parcialmente enmascarados en los logs
- Los tokens temporales de API se limpian automáticamente
- No se almacenan tokens en archivos de configuración
- El token se obtiene dinámicamente en cada deployment

## ⚡ Beneficios

1. **Sin Configuración Manual**: No necesitas obtener tokens manualmente
2. **Resiliente**: Múltiples métodos de fallback
3. **Seguro**: Tokens temporales y limpieza automática
4. **Automático**: Funciona out-of-the-box después del deployment de GitLab
5. **Robusto**: Validaciones y verificaciones en cada paso