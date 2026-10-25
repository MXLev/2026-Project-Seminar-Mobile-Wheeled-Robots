# Практическая работа 1. Знакомство с ROS2

Вариант **13**: две черепахи в `turtlesim` рисуют число **13** (цифры `1` и `3`) набором прямых отрезков
в стиле семисегментного индикатора. Условие задания: [TASK.md](TASK.md).

## Состав пакета `practice1_turtlesim`

| Файл | Назначение |
| --- | --- |
| `practice1_turtlesim/digit_drawer.py` | Универсальная управляющая программа: одна нода управляет **одной** черепахой и рисует **одну** цифру. |
| `practice1_turtlesim/digits.py` | Описание начертаний цифр `1` и `3` (ломаные из прямых отрезков; допускается повторный проход отрезков). |
| `practice1_turtlesim/scene_setup.py` | Вспомогательная нода: вызывает сервисы `/kill` (удаляет `turtle1`) и `/spawn` (создаёт двух новых черепах), затем завершается. |
| `launch/practice1.launch.py` | Единственный launch-файл, запускающий всю систему. |

### Как работает управляющая программа

Цифра представлена последовательностью действий: *повернуться до абсолютного угла → проехать отрезок → повернуться → проехать …*

- нода подписывается на `/<turtle_name>/pose` и публикует `geometry_msgs/msg/Twist` в `/<turtle_name>/cmd_vel` с частотой 50 Гц;
- поворот завершается, когда `theta` из `pose` отличается от целевого угла меньше чем на `angle_tolerance`;
- перед прямолинейным движением запоминается начальная точка `(x, y)`, движение завершается, когда расстояние
  `sqrt((x - x_start)^2 + (y - y_start)^2)` достигает длины отрезка (с допуском `distance_tolerance`);
  у конца отрезка/поворота скорость плавно уменьшается, чтобы не «проскочить» цель;
- переход между действиями определяется только данными `pose`, а не временем; телепортация не используется;
- после завершения рисунка нода остаётся запущенной и публикует нулевые линейную и угловую скорости.

Параметры `digit_drawer` (ROS2 parameters):

| Параметр | По умолчанию | Описание |
| --- | --- | --- |
| `turtle_name` | `turtle1` | имя черепахи (топики `/<имя>/pose`, `/<имя>/cmd_vel`) |
| `digit` | `1` | рисуемая цифра (реализованы `1` и `3`) |
| `origin_x`, `origin_y` | `1.0`, `3.0` | левый нижний угол области цифры в координатах `turtlesim` |
| `width`, `height` | `3.0`, `6.0` | размеры области цифры |
| `linear_speed`, `angular_speed` | `2.0`, `2.5` | максимальные скорости |
| `angle_tolerance`, `distance_tolerance` | `0.005`, `0.01` | допуски завершения поворота и отрезка |
| `rate_hz` | `50.0` | частота управления |

### Что делает launch-файл

1. Запускает `turtlesim_node`.
2. Запускает `scene_setup`: он ждёт сервисы, удаляет `turtle1` через `/kill` и создаёт черепах `turtle_left` и `turtle_right`
   через `/spawn` (каждую в начальной точке своей цифры).
3. После успешного завершения `scene_setup` запускает два экземпляра `digit_drawer`:
   `drawer_left` (`turtle_left`, цифра `1`) и `drawer_right` (`turtle_right`, цифра `3`).

Никакой ручной подготовки сцены не требуется.

## Сборка и запуск

Работа выполняется в Docker-контейнере курса (см. корневой `README.md` репозитория). Папка `practices/`
примонтирована в контейнер как `~/practices_ws/src/`.

1. На хосте запустите контейнер (команды запуска и `exec` из корневого `README.md`) и откройте оболочку в контейнере.
2. Соберите пакет (в контейнере):

   ```bash
   cd ~/practices_ws
   colcon build --symlink-install --packages-select practice1_turtlesim
   source install/setup.zsh
   ```

3. Запустите систему одной командой:

   ```bash
   ros2 launch practice1_turtlesim practice1.launch.py
   ```

   В окне `turtlesim` две черепахи нарисуют `13`, после чего останутся на месте (ноды продолжают публиковать нулевую скорость).
   Остановка: `Ctrl+C` в терминале с launch-файлом.

Проверка стиля кода (в контейнере):

```bash
colcon test --packages-select practice1_turtlesim && colcon test-result --verbose
```

## Диагностика

В соседнем терминале контейнера (после `source ~/practices_ws/install/setup.zsh`):

```bash
ros2 node list                          # /turtlesim, /drawer_left, /drawer_right
ros2 node info /drawer_left             # подписка на /turtle_left/pose, публикация в /turtle_left/cmd_vel
ros2 topic list -t                      # топики /turtle_left/... и /turtle_right/...
ros2 topic echo /turtle_right/pose      # текущее положение второй черепахи
ros2 topic echo /turtle_right/cmd_vel   # команды движения (после рисунка - нули)
ros2 topic hz /turtle_left/cmd_vel      # ~50 Гц
ros2 service list | grep -E 'kill|spawn'
rqt_graph                               # граф узлов и топиков
```

В `rqt_graph` (режим `Nodes only`, обновите граф кнопкой refresh после окончания рисования) видны узлы
`/drawer_left` и `/drawer_right`, связанные с `/turtlesim` топиками `/turtle_left/{pose,cmd_vel}` и `/turtle_right/{pose,cmd_vel}`.
