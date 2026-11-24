# vllm-ops-kit

[English version](README.md)

Проєкт розгортання та перевірки [Verstak Agent](https://github.com/Galactic717/verstak-agent) і [Verifine SLM](https://github.com/Galactic717/verifine-slm). Підключайте GGUF у Windows через llama.cpp, запускайте повний CPU-стек у kind або розгортайте vLLM із моделлю Safetensors у Kubernetes із NVIDIA GPU.

| Профіль | Модель | Що перевіряє |
|---|---|---|
| Windows | Локальна GGUF через llama.cpp | Генерація, SSE, токени й метрики шлюзу Verifine |
| kind | Детермінована CPU-фікстура | Ingress, OAuth, Celery, PostgreSQL, Redis, NetworkPolicy, Prometheus, Grafana, HPA та k6 |
| Ubuntu VM | CPU-фікстура | Terraform, Ansible, Docker Compose, systemd, TLS-проксі та Node Exporter |
| GPU Kubernetes | vLLM із моделлю на PVC | Ті самі API, метрики генерації та виділений GPU |

## Локальний запуск у Windows

Запустіть свій лаунчер llama.cpp і Docker Desktop. Зберіть образи із сусідніх репозиторіїв. Для окремого клону виконайте `python scripts/images.py --fetch`, щоб отримати зафіксовані версії проєктів.

~~~powershell
python scripts/images.py
pwsh -File scripts/local.ps1 -Port 9941
~~~

Укажіть порт вашого лаунчера. Скрипт визначає ідентифікатор моделі автоматично й піднімає тимчасовий шлюз Verifine. Якщо сервер вимагає ключ, передайте його через змінну середовища LLAMA_API_KEY.

У наявних лаунчерах Gemma E4B відповідає на 9931, Gemma 12B на 9932, GPT-OSS 20B на 9933 і GPT-OSS 120B на 9939. Порт 9934 спільний для лаунчерів Gemma 26B і GLM. Під час ручного вибору шляху скрипт сам запускає тимчасовий CPU-сервер.

~~~powershell
$model = Get-ChildItem "$env:LOCALAPPDATA/Programs/llama.cpp/models" -Recurse -Filter 'gemma-4-E4B-it-UD-Q8_K_XL.gguf' | Select-Object -First 1
pwsh -File scripts/local.ps1 -Port 18091 -ModelPath $model.FullName
~~~

## Перевірка Kubernetes

Потрібні Linux-контейнери на amd64, Docker 28+ із API 1.48, Python 3.10+, Git, kind 0.30.0, kubectl 1.34, Helm 3.19 і k6 1.3. Виділіть Docker щонайменше 4 CPU та 8 ГіБ памʼяті. У Linux інструменти можна встановити скриптом [ci_tools.sh](scripts/ci_tools.sh).

У Windows встановіть інструменти в каталог проєкту й додайте їх до поточного сеансу PowerShell.

~~~powershell
pwsh -File scripts/install-windows-tools.ps1
$env:PATH = "$(Join-Path $PWD '.tools/bin');$env:PATH"
~~~

~~~sh
python scripts/images.py --fetch
python scripts/kind_lab.py
~~~

До кінцевих точок лабораторії можна звертатися за адресою 127.0.0.1:18080. Результати й дані HPA записуються до loadtest/results/latest. Для повторної перевірки виконайте `python scripts/kind_lab.py --verify-only`. Щоби прибрати лабораторію, виконайте `kind delete cluster --name vllm-ops-kit --kubeconfig .kubeconfig-kind`.

## Розгортання та експлуатація

- [AWS, GCP, OIDC, Ubuntu й GPU-профіль](docs/CLOUD.md)
- [Архітектура, секрети, мережа та метрики](docs/ARCHITECTURE.md)
- [Місце на диску](docs/runbooks/disk-pressure.md), [OOMKilled](docs/runbooks/oomkilled.md), [Redis](docs/runbooks/redis-down.md), [блокування PostgreSQL](docs/runbooks/db-lock.md) і [HTTP 429 від LLM](docs/runbooks/llm-429.md)

## Виміряно

[Звіт перевірки](loadtest/results/README.md) містить результати локальної генерації в Windows, базового навантаження та 3× піка в kind. GitHub Actions і GitLab повторюють перевірки й зберігають артефакти прогонів та звіти сканерів.
