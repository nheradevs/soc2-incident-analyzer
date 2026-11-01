# Despliegue en un único servidor (GCP Compute Engine, e2-micro)

Esta guía asume que **ya tienes** un proyecto de GCP y una instancia creada. Cubre lo que falta
para que el analizador SOC L2 quede publicado desde el repositorio de GitHub en una sola máquina.

La máquina objetivo es una **e2-micro**: 1 GB de RAM, 2 vCPU compartidas y 30 GB de disco. La
aplicación cabe de sobra en ejecución —medido con el export de ejemplo, el API llega a **~134 MB**
de pico y Caddy a **~15 MB**—, pero **la compilación de Angular no cabe**: por eso el `Dockerfile`
es multi-etapa y compila el frontend con `NODE_OPTIONS=--max-old-space-size=768`, y por eso el
paso 3 (swap de 2 GB) **no es opcional** si vas a construir en la propia VM.

Arquitectura del despliegue:

```
Internet ──► Caddy (contenedor `web`, único publicado: 80 y 443)
                 ├── /            → estáticos del bundle Angular (/srv)
                 ├── /cargar /analisis /informe → index.html (SPA)
                 └── /api/*       → reverse_proxy api:8000
                                        │
                                        └── contenedor `api` (FastAPI, sin puertos publicados)
```

El contenedor `api` **no se publica**: solo Caddy lo alcanza por la red interna de compose. No hay
secretos en `docker-compose.yml`; la clave del proveedor, si la usas, entra por variable de
entorno.

---

## 1. Reglas de firewall para 80 y 443

Con `gcloud` (sustituye `soc2-web` por el tag que uses en la instancia):

```bash
gcloud compute firewall-rules create soc2-web \
  --allow tcp:80,tcp:443 \
  --source-ranges 0.0.0.0/0 \
  --target-tags soc2-web \
  --description "SOC L2 analyzer: HTTP y HTTPS"
```

Y etiqueta la instancia con `soc2-web` (Consola → instancia → Editar → *Network tags*):

```bash
gcloud compute instances add-tags NOMBRE_DE_LA_INSTANCIA --zone=ZONA --tags=soc2-web
```

La regla `default-allow-ssh` (puerto 22) ya existe en los proyectos nuevos; si no, créala solo
para tu IP. **No abras el 8000**: el API no debe ser accesible desde Internet.

## 2. IP externa estática

Una IP efímera cambia al parar y arrancar la instancia, y con ella cambia la URL que compartes.

```bash
# Reserva una IP en la misma región que la instancia
gcloud compute addresses create soc2-ip --region=REGION

# Consulta la IP reservada
gcloud compute addresses describe soc2-ip --region=REGION --format='get(address)'

# Asígnasela a la instancia
gcloud compute instances delete-access-config NOMBRE_DE_LA_INSTANCIA \
  --zone=ZONA --access-config-name="External NAT"
gcloud compute instances add-access-config NOMBRE_DE_LA_INSTANCIA \
  --zone=ZONA --access-config-name="External NAT" \
  --address=IP_RESERVADA
```

En la consola equivale a *Editar → Interfaces de red → IP externa → Crear dirección IP → Estática*.

## 3. Swap de 2 GB (obligatorio en una e2-micro)

`npm ci` + `ng build` necesitan más de 1 GB aunque el heap de Node esté limitado a 768 MB: el
resto lo consumen el propio Node fuera del heap, esbuild y el sistema. Sin swap, `docker compose
build` muere con `Killed` (OOM) a mitad de la etapa de frontend.

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Persistente tras reiniciar
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Comprobar
free -h
swapon --show
```

Añade también, para que el kernel no expulse el proceso del API a swap con el disco lleno de
páginas:

```bash
echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-soc2-swap.conf
sudo sysctl --system
```

## 4. Instalar Docker y el plugin de compose

Ubuntu 22.04/24.04 LTS (repositorio oficial de Docker, no el paquete `docker.io` de Ubuntu, que no
trae `docker compose`):

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Usar docker sin sudo (cierra y abre la sesión después)
sudo usermod -aG docker "$USER"

# Comprobar que el plugin está instalado y es v2 (cualquier versión reciente vale)
docker compose version
```

## 5. Clonar el repositorio

```bash
sudo apt-get install -y git
git clone https://github.com/ORG/REPO.git soc2
cd soc2
```

El repositorio incluye el export de ejemplo
(`SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx`), así que puedes probar el flujo completo sin
subir nada desde tu equipo.

## 6. (Opcional) clave del proveedor para la redacción asistida

El informe está completo sin clave: el estado de la narrativa será `no_configurada` y el texto lo
escribe el motor de reglas. Si quieres habilitar la reescritura asistida, **no edites
`docker-compose.yml`**: crea un `.env` en la raíz del repositorio (está en `.gitignore`) y compose
lo leerá para interpolar la variable:

```bash
printf 'NAN_API_KEY=%s\n' 'TU_CLAVE' >> .env
chmod 600 .env
```

`NAN_BASE_URL` y `NAN_MODEL` también se pueden fijar ahí. La clave nunca llega al navegador ni
queda escrita en la imagen.

## 7. Construir y arrancar

```bash
docker compose up -d --build
```

La primera construcción en una e2-micro tarda **del orden de 10 a 20 minutos** (estimación para
2 vCPU compartidas y swap sobre disco de red): descarga de imágenes, `npm ci` y `ng build`. Como
referencia, en una máquina de desarrollo con 12 núcleos y 23 GB de RAM el mismo
`docker compose build` tardó **42 s** en frío. Las siguientes construcciones reutilizan la caché de
capas y tardan segundos si no cambia el `package-lock.json` ni el `uv.lock`.

Tamaños medidos de las dos imágenes:

| Imagen | Tamaño |
|---|---|
| `soc2-analyzer-api:local` | ~555 MB |
| `soc2-analyzer-web:local` | ~94 MB |

Estado y registro:

```bash
docker compose ps
docker compose logs -f api
docker compose logs -f web
```

## 8. Comprobar que está vivo

```bash
# El API responde a través de Caddy
curl -fsS http://IP_ESTATICA/api/health          # {"status":"ok"}

# El shell de la SPA se sirve en las tres rutas del cliente (200, no 404)
for r in /cargar /analisis /informe; do
  curl -s -o /dev/null -w "$r -> %{http_code}\n" "http://IP_ESTATICA$r"
done

# Flujo completo de extremo a extremo
curl -fsS -F "file=@SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx" http://IP_ESTATICA/api/upload
curl -fsS -X POST http://IP_ESTATICA/api/analyze
curl -fsS -X POST http://IP_ESTATICA/api/report
curl -fsS -o informe.pdf http://IP_ESTATICA/api/report/pdf
```

Medido sobre esta imagen con la export de ejemplo: 715 filas, 6 incidentes, dos versiones de
informe con 9 secciones cada una y un PDF de 46.475 bytes.

El estado de la sesión (la export cargada, su análisis y el informe compuesto) vive **en memoria
del proceso del API**: hay un único contenedor `api`, así que subir el archivo una vez basta para
`/analisis` y `/informe`, pero **no escales `api` a más de una réplica** ni lo reinicies entre la
subida y la descarga del PDF: se pierde la sesión y hay que volver a subir el archivo. Un reinicio
del contenedor también la borra (es el comportamiento documentado de la demo, no un fallo del
despliegue).

## 9. Actualizar tras un `git push`

En tu equipo:

```bash
git push
```

En la VM:

```bash
cd ~/soc2
git pull --ff-only
docker compose up -d --build
docker image prune -f          # borra las capas viejas que ya no usa nadie
```

`docker compose up -d --build` reconstruye solo lo que cambió y recrea los contenedores; hay unos
segundos de corte. Como el estado de sesión es en memoria, quien estuviera a mitad de un análisis
tendrá que volver a subir el archivo.

Para liberar espacio en los 30 GB del disco:

```bash
docker system df               # cuánto ocupan imágenes, contenedores y caché de build
docker builder prune -f        # caché de construcción (se regenera en el siguiente build)
```

## 10. HTTPS con un dominio real

Con una IP y sin dominio, el despliegue sirve HTTP en el 80. Para HTTPS automático (Let's Encrypt,
renovación incluida) hacen falta un dominio y los puertos 80 y 443 abiertos:

1. Crea un registro `A` de `analizar.tudominio.com` apuntando a la IP estática.
2. En el `Caddyfile`, comenta el bloque `:80 { … }` y descomenta el bloque del dominio real
   (`analizar.tudominio.com { … }`), que ya trae los mismos manejadores.
3. `docker compose up -d` (Caddy recarga la configuración al recrearse el contenedor).

Caddy pide el certificado en el primer arranque y lo guarda en el volumen `caddy_data`, así que
sobrevive a `docker compose down`. No se necesita certbot ni ningún otro servicio.

## 11. Límite de peticiones detrás del proxy: qué hace este despliegue

El API limita las peticiones caras (subida, análisis, informe y PDF) con un contador en memoria
**por cliente y por endpoint**, y para identificar al cliente usa la dirección del par TCP
(`request.client.host`). Los cabeceros `X-Forwarded-For` / `X-Real-IP` no se leen en el código de la
aplicación: si se confiara en ellos sin más, cualquiera podría inventar una IP distinta en cada
petición y saltarse el límite.

Consecuencia detrás de un proxy: **si Caddy no reenvía la dirección del cliente, todas las
peticiones llegan al API desde la IP del contenedor `web` y comparten un único contador**. Los
límites por defecto (20 subidas, 120 análisis, 60 informes y 30 PDF por minuto) se agotarían entre
todos los usuarios a la vez, y un solo visitante podría dejar sin PDF a los demás.

Qué hace este despliegue, sin tocar el código de la aplicación:

1. `docker-compose.yml` fija la dirección del contenedor `web` (`172.28.0.10`) en una red propia.
2. El servicio `api` arranca uvicorn con `--proxy-headers` y `FORWARDED_ALLOW_IPS=172.28.0.10`.
   uvicorn reescribe entonces la dirección del par con el valor de `X-Forwarded-For`, pero **solo
   si la conexión viene de esa IP**: un cliente que llegue por otro camino no puede falsearla.
3. Caddy añade `X-Forwarded-For`, `X-Forwarded-Proto` y `X-Forwarded-Host`, y **sobrescribe** el
   `X-Forwarded-For` que envíe el navegador, así que la cabecera no se puede falsificar a través
   del proxy.
4. El puerto 8000 del API no se publica: nadie puede hablar con uvicorn saltándose Caddy.

Resultado: cada navegador conserva su propio contador y el límite sigue teniendo sentido detrás del
proxy. Comprobado en el despliegue: el API registra la IP real del cliente (`127.0.0.1` en la
prueba local) en lugar de la del contenedor `web`, y al agotar el cupo de PDF responde
`429` con `Retry-After` solo a ese cliente.

Si cambias la subred o la IP de la red de compose, actualiza **las dos** referencias a la vez
(`FORWARDED_ALLOW_IPS` en `api` e `ipv4_address` en `web`). Si prefieres no confiar en la cabecera,
borra `FORWARDED_ALLOW_IPS`: el valor por defecto de uvicorn (`127.0.0.1`) hace que todas las
peticiones compartan un solo contador, que es el comportamiento seguro pero incómodo con varios
usuarios.

## 12. Operación diaria

```bash
docker compose ps                     # estado y salud de los contenedores
docker compose logs --tail=100 api    # errores del API
docker compose restart api            # reinicio del API (borra la sesión en memoria)
docker compose down                   # parar y borrar los contenedores (conserva los volúmenes)
docker compose up -d                  # volver a arrancar con las mismas imágenes
```

`docker compose down` **conserva** los volúmenes `caddy_data` y `caddy_config` (certificados). Solo
`docker compose down -v` los borra, y con ellos el certificado, que Caddy volvería a pedir.

El `healthcheck` del servicio `api` consulta `/api/health` cada 15 s; el servicio `web` no arranca
hasta que `api` está sano, así que tras un reinicio de la VM Caddy espera al backend en lugar de
devolver 502.

## 13. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `docker compose build` termina con `Killed` o `signal: killed` en la etapa de frontend | Falta swap (paso 3) o el heap de Node se quedó sin margen. Comprueba `free -h` y repite. |
| `failed to bind host port 0.0.0.0:80`: address already in use | Otro proceso o contenedor ocupa el 80 (por ejemplo un servidor web ya instalado en la VM). Libéralo o cambia el mapeo de puertos del servicio `web`. |
| `502 Bad Gateway` en `/api/*` | El contenedor `api` no está sano: `docker compose logs api`. Suele ser un `Killed` por memoria. |
| `curl http://IP/api/health` no conecta | La regla de firewall del paso 1 no está aplicada a la instancia, o el tag no coincide. |
| `/cargar` devuelve 404 | El bundle no se copió a la imagen `web`: reconstruye con `docker compose build --no-cache web`. |
| `429 Demasiadas solicitudes` con pocos usuarios | Revisa el paso 11: si tocaste la red de compose, `FORWARDED_ALLOW_IPS` ya no coincide con la IP de `web`. |
