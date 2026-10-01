# Практическая работа 2. Знакомство с Webots

Вариант **13**: в центре площадки 6 × 6 м стоят два статических препятствия в форме цифр **1** и **3**,
робот TurtleBot3 Burger объезжает их по окружности. Условие задания: [TASK.md](TASK.md).

## Состав пакета `practice2_webots`

| Файл | Назначение |
| --- | --- |
| `worlds/number_13.wbt` | Сцена: площадка `RectangleArena` 6 × 6 м со стенами, цифры `1` и `3`, робот TurtleBot3 Burger. |
| `protos/Digit1.proto` | PROTO цифры `1`: стойка, флажок и основание из `Box`. |
| `protos/Digit3.proto` | PROTO цифры `3` в стиле семисегментного индикатора: три горизонтальных и один вертикальный сегмент из `Box`. |
| `launch/number_world.launch.py` | Основной launch-файл: Webots со сценой, драйвер робота, `robot_state_publisher` и контроллеры колёс. |
| `launch/circle_motion.launch.py` | Дополнительный launch-файл: включает основной и публикует постоянную скорость в `/cmd_vel`. |

`setup.py` устанавливает каталоги `launch`, `worlds` и `protos` в `share/practice2_webots`, поэтому сцена
открывается сразу после сборки, без ручных действий в Webots.

### Сцена

- Площадка 6 × 6 м, высота стен 0.4 м, центр площадки — начало координат.
- Цифры серые, высотой 0.3 м, размер каждой примерно 0.8 × 1.4 м, толщина сегментов 0.15 м.
  Число читается слева направо вдоль оси `X`, верх цифр направлен по оси `Y`.
  Центр цифры `1` — `(-0.6, 0)`, цифры `3` — `(0.6, 0)`, между цифрами около 0.45 м свободного места.
- Цифры — экземпляры `Digit1` и `Digit3`, подключённые через `EXTERNPROTO "../protos/..."`.
  В PROTO заданы геометрия и `boundingObject`, но нет узла `Physics`, поэтому цифры статические:
  робот не может их сдвинуть или проехать сквозь них.
- Робот появляется в точке `(0, -1.8)` и смотрит вдоль оси `X`, то есть стоит на окружности радиуса 1.8 м
  вокруг центра числа.

### Движение по окружности

При постоянных линейной `v` и угловой `w` скоростях робот движется по окружности радиуса `R = v / w`.
Используются `v = 0.18` м/с (ограничение контроллера TurtleBot3 — 0.2 м/с) и `w = 0.1` рад/с, тогда `R = 1.8` м,
а полный круг занимает `2π / w ≈ 63` с. Робот объезжает число против часовой стрелки.

Проверка по GPS робота в Webots: за круг радиус траектории остаётся в пределах 1.79–1.80 м,
центр робота проходит не ближе 0.57 м от цифр и не ближе 1.2 м от стен.

## Сборка и запуск

Работа выполняется в Docker-контейнере курса со средой Webots (см. корневой `README.md` репозитория).
Папка `practices/` примонтирована в контейнер как `~/practices_ws/src/`.
На Mac перед запуском должен работать сервер Webots `local_simulation_server.py`.

1. Соберите пакет (в контейнере):

   ```bash
   cd ~/practices_ws
   colcon build --symlink-install --packages-select practice2_webots
   source install/setup.zsh
   ```

2. Запустите симуляцию одной командой:

   ```bash
   ros2 launch practice2_webots number_world.launch.py
   ```

   Откроется Webots со сценой. Дождитесь в логе сообщений
   `Configured and activated diffdrive_controller` и `Configured and activated joint_state_broadcaster`.

3. Во втором терминале контейнера запустите движение по окружности:

   ```bash
   ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/TwistStamped "{header: {stamp: {sec: 0, nanosec: 0}, frame_id: 'base_link'}, twist: {linear: {x: 0.18, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.1}}}"
   ```

   Остановка движения: `Ctrl+C` в этом терминале. Завершение симуляции: `Ctrl+C` в терминале с launch-файлом.

Вместо шагов 2 и 3 можно запустить сцену и движение одним launch-файлом:

```bash
ros2 launch practice2_webots circle_motion.launch.py
```

Скорости можно изменить аргументами, например `linear_speed:=0.15 angular_speed:=0.0833`.

Проверка стиля кода (в контейнере):

```bash
colcon test --packages-select practice2_webots && colcon test-result --verbose
```

## Диагностика

```bash
ros2 control list_controllers                          # diffdrive_controller и joint_state_broadcaster active
ros2 topic echo /odom --field pose.pose.position       # положение по одометрии (от точки старта)
ros2 topic echo /TurtleBot3Burger/gps --field point    # положение робота в координатах сцены
```

Если после `Ctrl+C` в контейнере остался процесс драйвера `webots_ros2_driver/driver`, следующий запуск
не сможет загрузить контроллеры (`Failed loading controller ...`). В этом случае завершите его перед новым запуском:

```bash
pkill -f webots_ros2_driver/driver
```
