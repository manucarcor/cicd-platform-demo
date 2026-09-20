# CI/CD Platform on Kubernetes (demo)

Demo/training de despliegue automatizado con **Ansible + Helm** de una
plataforma CI/CD completa sobre Kubernetes: **Traefik** (ingress), **Jenkins**,
**GitLab CE** (con su **Runner**, registrado automáticamente) y **Nexus**
(artefactos/registry).


## 📘 Índice

* [El problema](#el-problema)
* [La solución](#la-solución)
* [Arquitectura](#️-arquitectura)
* [Requisitos previos](#️-requisitos-previos)
* [Configuración de secretos](#-configuración-de-secretos)
* [Puesta en marcha](#-puesta-en-marcha)
* [Variables de entorno / inventario](#-variables-de-entorno--inventario)
* [Testing automatizado](#-testing-automatizado)
* [Estructura del repositorio](#-estructura-del-repositorio)
* [Licencia](#licencia)

---

## El problema

Montar una plataforma de CI/CD self-hosted sobre Kubernetes —en vez de usar
SaaS gestionado— implica coordinar varias piezas que no vienen conectadas
entre sí:

- Desplegar cada servicio (Jenkins, GitLab CE, Nexus, un ingress) con sus
  propios requisitos de persistencia, recursos, TLS y RBAC.
- Publicarlos todos detrás de un único ingress, con certificados por
  servicio.
- Registrar un GitLab Runner contra la instancia de GitLab recién
  desplegada — normalmente un paso manual (copiar un token desde la UI)
  que rompe la automatización end-to-end.
- Gestionar credenciales de administración de cuatro servicios distintos
  sin dejarlas en texto plano en el repositorio.
- Poder repetir el despliegue igual en varios entornos (lab, staging,
  producción) sin duplicar la lógica de cada rol.
- Verificar que lo desplegado realmente funciona, no solo que el `helm
  install` no dio error.

## La solución

Este proyecto automatiza todo el ciclo con **Ansible**, en **roles**
independientes por servicio (`role_traefik`, `role_jenkins`, `role_gitlab`,
`role_gitlab_runner`, `role_nexus`) que comparten una lógica común de
despliegue Helm (`common_tasks`) para namespace, TLS y `helm upgrade
--install` idempotente.

El punto más particular es **`role_gitlab_runner`**: en vez de pedir el
token de registro a mano en la UI de GitLab, el rol espera a que GitLab
esté listo y lo obtiene automáticamente (API, y si falla, acceso directo a
Rails/BD como fallback), para que `Step02-deploy.yml` despliegue la
plataforma completa en una sola pasada sin intervención manual.

Los secretos se gestionan con **Ansible Vault**: nunca se versionan en
texto plano, solo se documenta qué variables `secret_*` hacen falta (ver
`secret.yml.example`). Y hay un **role de testing** (`role_cicd_tests`)
que, tras el despliegue, ejecuta una suite `pytest` contra cada servicio
para verificar que de verdad está sano (pods `Running`, API respondiendo,
RBAC del runner creado, etc.), no solo que Ansible no reportó error.

---

## 🏛️ Arquitectura

```mermaid
flowchart TB
    Internet((Cliente / CI))

    subgraph K8s["Clúster Kubernetes (inventario service-cluster-lab)"]
        Traefik[Traefik\ningress controller]

        subgraph NsJenkins["ns: jenkins"]
            Jenkins[Jenkins]
        end
        subgraph NsGitlab["ns: gitlab"]
            GitLab[GitLab CE]
        end
        subgraph NsRunner["ns: gitlab-runner"]
            Runner[GitLab Runner]
        end
        subgraph NsNexus["ns: nexus"]
            Nexus[Nexus\nartefactos/registry]
        end
    end

    Internet -->|HTTPS| Traefik
    Traefik --> Jenkins
    Traefik --> GitLab
    Traefik --> Nexus

    Runner -.->|obtiene token vía API\n(automático)| GitLab
    Runner -->|ejecuta jobs| K8s

    Ansible[["Ansible\n(Step01 → Step02 → Step03)"]] -->|helm upgrade --install| Traefik
    Ansible --> Jenkins
    Ansible --> GitLab
    Ansible --> Runner
    Ansible --> Nexus
    Ansible -.->|pytest post-deploy| NsJenkins
    Ansible -.->|pytest post-deploy| NsGitlab
    Ansible -.->|pytest post-deploy| NsNexus

    Nexus -.->|charts Helm internos| Ansible
```

---

## ⚙️ Requisitos previos

- Un clúster Kubernetes ya operativo y accesible (`kubectl`/kubeconfig
  configurado) — este repo despliega *sobre* un clúster, no lo crea (para
  eso, ver el proyecto de bootstrap RKE2+Rancher del resto del portfolio).
- Ansible ≥ 2.15 y la colección `kubernetes.core`
  (`ansible-galaxy collection install kubernetes.core`).
- `helm` ≥ 3 (Step01 lo instala automáticamente si no está).
- `kubectl` y `python3` en el nodo desde el que se ejecuta Ansible.
- Para `Step03-test.yml`: `python3 -m venv` + `pip install -r
  roles/role_cicd_tests/files/requirements.txt` (pytest + kubernetes
  client). El role lo gestiona por ti, ver
  [`roles/role_cicd_tests/README.md`](roles/role_cicd_tests/README.md).

## 🔐 Configuración de secretos

```bash
# 1. Copia la plantilla y rellena valores reales
cp inventories/service-cluster-lab/group_vars/all/secret.yml.example \
   inventories/service-cluster-lab/group_vars/all/secret.yml

# 2. Edita secret.yml con tus contraseñas/tokens reales, luego cífralo
ansible-vault encrypt inventories/service-cluster-lab/group_vars/all/secret.yml

# Para editarlo más tarde:
ansible-vault edit inventories/service-cluster-lab/group_vars/all/secret.yml
```

Guarda la contraseña de vault en un gestor de contraseñas o en un fichero
`.vault_pass` fuera de git (ya está en `.gitignore`) — nunca la subas al
repositorio.

## 🚀 Puesta en marcha

```bash
# 1. Requisitos: instala la colección de Ansible, helm y añade los repos Helm
ansible-playbook -i inventories/service-cluster-lab/hosts.ini Step01-requirements.yml --ask-vault-pass

# 2. Despliega la plataforma completa (Traefik, Jenkins, GitLab, Runner, Nexus)
ansible-playbook -i inventories/service-cluster-lab/hosts.ini Step02-deploy.yml --ask-vault-pass

# 2b. O despliega solo un servicio con --tags
ansible-playbook -i inventories/service-cluster-lab/hosts.ini Step02-deploy.yml --tags gitlab --ask-vault-pass

# 3. Verifica que todo quedó sano (pytest contra Jenkins/Nexus/GitLab)
ansible-playbook -i inventories/service-cluster-lab/hosts.ini Step03-test.yml --ask-vault-pass
```

Con `cluster_domain` por defecto (`cicd.example.test`), los servicios
quedan accesibles vía Traefik en `https://jenkins.cicd.example.test`,
`https://gitlab.cicd.example.test` y `https://nexus.cicd.example.test`
(ajusta DNS/`/etc/hosts` según tu entorno).

## 🔧 Variables de entorno / inventario

Configuración global relevante en `inventories/service-cluster-lab/group_vars/all/all.yml`:

| Variable | Descripción | Ejemplo |
|---|---|---|
| `cluster_domain` | Dominio base para los ingress de todos los servicios | `cicd.example.test` |
| `storage_class` | StorageClass usada para la persistencia de Jenkins/GitLab/Nexus | `nfs-storage` |
| `registry` / `registry_username` | Registry Docker privado para el `imagePullSecret` | `docker-registry.example.org` |
| `registry_snapshots` / `registry_releases` | Repositorios Helm internos donde viven los charts de cada servicio | `https://nexus.example.org/repository/helm-snapshots` |
| `ingress_controller` | `nginx` o `traefik` | `nginx` |
| `*_chart_version` | Versión del chart Helm de cada servicio (SNAPSHOT/release) | `0.0.1-SNAPSHOT` |
| `*_resources_limits_cpu/memory` | Límites de recursos por servicio | ver `all.yml` |

Todas las contraseñas (`secret_*`) viven en `secret.yml` cifrado — ver
[Configuración de secretos](#-configuración-de-secretos) y el listado
completo en `secret.yml.example`.

## ✅ Testing automatizado

`role_cicd_tests` auto-descubre el pod del servicio desplegado (por label
`app.kubernetes.io/name=<servicio>-chart`) y ejecuta una suite `pytest`
específica contra él (`test_jenkins_checks.py`,
`test_gitlab_checks.py`, `test_gitlab_runner_checks.py`,
`test_nexus_checks.py`), parseando el resultado JUnit para un resumen
legible. Detalle completo en
[`roles/role_cicd_tests/README.md`](roles/role_cicd_tests/README.md).

```bash
# Test de un servicio concreto
ansible-playbook -i inventories/service-cluster-lab/hosts.ini Step03-test.yml --tags gitlab --ask-vault-pass
```

---

## 📁 Estructura del repositorio

```
.
├── Step01-requirements.yml   # instala colección Ansible, helm, repos Helm
├── Step02-deploy.yml         # despliega Traefik/Jenkins/GitLab/Runner/Nexus
├── Step03-test.yml           # pytest post-deploy contra cada servicio
├── ansible.cfg
├── inventories/
│   └── service-cluster-lab/
│       ├── hosts.ini                      # nodos, usuario, credenciales (via vault)
│       └── group_vars/all/
│           ├── all.yml                    # config no sensible de los 5 servicios
│           └── secret.yml.example         # variables secret_* documentadas
├── roles/
│   ├── common_tasks/       # namespace, TLS, helm upgrade --install reutilizable
│   ├── role_traefik/       # ingress controller
│   ├── role_jenkins/
│   ├── role_gitlab/        # incluye reset de password root post-instalación
│   ├── role_gitlab_runner/ # registro automático de token (ver su propio README)
│   ├── role_nexus/
│   └── role_cicd_tests/    # suite pytest + auto-discovery de pods
└── scripts/
    └── deploy-gitlab-runner.sh   # ejemplo de despliegue solo del runner
```



## Licencia

MIT — ver [LICENSE](LICENSE).
