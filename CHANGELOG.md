# Changelog

Todos los cambios notables de este proyecto de demo se documentan en este fichero.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/)
y este proyecto sigue [Semantic Versioning](https://semver.org/lang/es/spec/v2.0.0.html).


## [demo-1.0.0] - 2026-09-14

### Saneado para publicación
- **Credencial SSH/sudo real eliminada de `hosts.ini`.** `ansible_password`
  y `ansible_become_password` estaban en texto plano; movidas a Ansible
  Vault (`secret_ansible_password` / `secret_ansible_become_password`).
  `secret.yml` cifrado original sustituido por `secret.yml.example`, sin
  ningún valor real.
- **Identidad de cliente/consultora eliminada**: dominio (`chakray.test` →
  `cicd.example.test`), hostnames de nodos, usuario de despliegue, registry
  Docker/Helm interno, IPs privadas de ejemplo, y el prefijo `chk-` en
  todos los `chart_ref` de Helm, secretos de Kubernetes y selectores de
  label — incluida la suite `pytest` de `role_cicd_tests`, que hardcodeaba
  el prefijo en varias aserciones.
- **Virtualenv de Python (`roles/role_cicd_tests/.venv-cicd-tests/`)
  eliminado del repositorio** — venía commiteado con binarios reales
  porque `.gitignore` no cubría `venv/`/`.venv*/` (solo `env/`); corregido.
- **Bug real corregido**: `Step01-requirements.yml` registraba un
  repositorio Helm apuntando a `{{ helm_repository_url }}`, variable no
  definida en ningún sitio del inventario — habría fallado con "variable
  undefined" en cualquier ejecución. Corregido a `{{ registry_snapshots }}`,
  siguiendo el mismo patrón que usan el resto de repos Helm internos.
- **Dos secretos del vault sin usar** (`secret_gitlab_redis_password`,
  `secret_gitlab_postgres_password`, no referenciados por ningún role)
  documentados igualmente en `secret.yml.example`, marcados como legacy,
  en vez de eliminados en silencio.
- Añadidos `LICENSE` (MIT) y este `CHANGELOG.md` reestructurado.

**Nota:** el `secret.yml` cifrado original se descifró una sola vez, con la
contraseña de vault aportada para esta auditoría, únicamente para poder
documentar con precisión qué variables `secret_*` consume el código. Ningún
valor real se ha copiado a este repositorio ni a su documentación.
