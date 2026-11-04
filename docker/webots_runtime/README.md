# Общий Webots runtime

Исправление устанавливается при сборке `docker/Dockerfile` и используется всеми
пакетами, которые запускают стандартные `WebotsLauncher` и `WebotsController`.
В практиках не нужны собственные копии драйвера, дополнительные `source` или
специальные команды запуска. Обновление образа само по себе не меняет контейнеры
на других компьютерах.

## Поддерживаемая версия

ROS 2 Jazzy, `webots_ros2_driver` и `webots_ros2_control` **2025.0.0**.
Проверяемое окружение: Ubuntu 24.04 aarch64 в UTM, Docker, Webots R2025a на Mac
через `local_simulation_server.py` и общую папку. Другие схемы запуска требуют
отдельной проверки.

`build.py` получает официальный архив Cyberbotics, проверяет его SHA-256,
применяет `shutdown.patch` и собирает драйвер под архитектуру контейнера.
Готовые двоичные файлы в Git не хранятся. Если версия ROS-пакета или ожидаемый
фрагмент исходника изменились, сборка останавливается: патч нужно пересмотреть.

## Что исправлено

- SIGINT не прерывает чтение Webots TCP внутри контроллера. Обработчики ROS,
  Webots и встроенных Python-плагинов согласованы.
- Потоки `ros2_control` и плагины освобождаются до выключения ROS-контекста;
  интерпретатор Python завершается один раз после освобождения всех плагинов.
- Драйвер дожидается установки описания робота перед запуском контроллеров.
- `WebotsController` запускает драйвер напрямую, без промежуточного `ros2 run`.
- TCP-клиент при остановке ждёт завершения контроллеров своего launch, затем
  закрывает соединение. Таймаут и ошибки сервера остаются ошибками.
- Стандартный `Ros2Supervisor` освобождает Webots до завершения Python.
- Перезапуск контроллеров и супервизора по умолчанию задержан на 2 секунды:
  сервер успевает сообщить о закрытии Webots до создания новых процессов.
  Явно заданный `respawn_delay` по-прежнему имеет приоритет.

В `example_webots_odometry` отдельный небольшой узел `circle_command` заменяет
команду `ros2 topic pub`: он корректно завершает ROS-контекст по Ctrl+C.
Скорости остаются 0.2 м/с и 0.2 рад/с, публикация — 10 Гц по времени симуляции.

## Обновление окружения UTM → Mac

Останови активную симуляцию. На **Ubuntu-хосте UTM**, из корня репозитория,
используй те же env-файлы и Compose-слои, с которыми создан контейнер:

```bash
docker tag ros2-base:jazzy ros2-base:before-runtime-update

HOST_XAUTHORITY="$XAUTHORITY" docker compose \
  --env-file .env --env-file .env.local \
  -f docker-compose.yaml \
  -f docker-compose.gpu.yaml \
  -f docker-compose.webots-mac.yaml \
  build ros2-base

HOST_XAUTHORITY="$XAUTHORITY" docker compose \
  --env-file .env --env-file .env.local \
  -f docker-compose.yaml \
  -f docker-compose.gpu.yaml \
  -f docker-compose.webots-mac.yaml \
  up -d --no-build --force-recreate ros2-base
```

`XAUTHORITY` должен указывать на актуальный файл графического сеанса Ubuntu;
в настроенном UTM он определяется автоматически при входе. Сам файл `.env.local`
индивидуален для компьютера и не включается в Git. Не подставляй путь с Mac.

Пересоздание контейнера завершает его терминальные сеансы. Исходники остаются
в bind-mount на хосте; файлы, созданные только внутри контейнера, предварительно
сохрани. После входа в новый контейнер собери необходимые workspace, например
в **bash**:

```bash
source /opt/ros/jazzy/setup.bash
cd ~/examples_ws
colcon build --symlink-install
source install/setup.bash
cd ~/practices_ws
colcon build --symlink-install
source install/setup.bash
```

В zsh используй `setup.zsh`. Сервер симуляции на Mac запускается как раньше.
Команды `ros2 launch ...` не меняются.

## Проверка и откат

Внутри контейнера сведения об установке находятся в
`/opt/robotics/webots-runtime/manifest.json`, исходные заменённые файлы — в
`/opt/robotics/webots-runtime/upstream/`. Сам установщик предназначен для
Docker build, повторно запускать его в уже исправленном контейнере не нужно.

Проверка TCP-протокола и защиты от несовместимых исходников:

```bash
python3 -m pytest /opt/robotics/webots-runtime/test -q -p no:cacheprovider
```

Для отката верни сохранённый образ и пересоздай сервис той же командой Compose
с `--no-build`. Не используй `--build` при откате:

```bash
docker tag ros2-base:before-runtime-update ros2-base:jazzy
```

При переходе со старого частного исправления practice-03 нужно также вернуть
согласованные с прежним образом исходники из резервной копии. Не восстанавливай
файлы поверх более новых правок без сравнения.

Исходники патча основаны на
[webots_ros2 2025.0.0](https://github.com/cyberbotics/webots_ros2/tree/2025.0.0)
под Apache-2.0; сведения об авторах сохранены в исходных файлах.
