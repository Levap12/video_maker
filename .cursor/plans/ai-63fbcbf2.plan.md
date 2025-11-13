<!-- 63fbcbf2-d2ac-44b1-9bab-40652f487f04 d18977d3-4b72-4d16-ab4e-cb05d8aed056 -->
# План: Привязка подзадач к карточкам AI нарезки

## Цель

Связать подзадачи (clipping, compilation, shorts_creation) с конкретными файлами AI нарезки, чтобы каждая карточка показывала статусы своих подзадач.

## Изменения

### 1. Расширение структуры file_info в artifacts (`web/routes/tasks_api.py`)

- Добавить поле `sub_tasks` в `file_info` при создании файла
- Структура: `sub_tasks: { 'clipping': {...}, 'compilation': {...}, 'shorts_creation': {...} }`
- Каждая подзадача содержит: `status`, `message`, `progress`, `error`, `outputs`, `updated_at`

### 2. Генерация уникальных имен подзадач (`web/routes/tasks_api.py`, `web/routes/compilation.py`)

- Создать функцию `generate_subtask_name(file_info)` для генерации уникального имени
- Формат: `{subtask_type}_{system_prompt_id}_{user_prompt_id}_{timestamp}`
- Пример: `clipping_3bdf04d7-ed20-4e04-8571-f4885fd7287e_b07a3e61-617d-4044-9af0-1da80ef2ca2d_20251105_235441`

### 3. Обновление endpoints для работы с привязанными подзадачами

- `create_clips_from_ai`: передавать `file_info` для генерации имени подзадачи
- `create_compilation`: передавать `file_info` для генерации имени подзадачи
- `create_shorts`: передавать `file_info` для генерации имени подзадачи
- После создания подзадачи обновлять `file_info.sub_tasks` в artifacts

### 4. Обновление функций создания подзадач (`web/tasks/clipping_task.py`, `web/tasks/compilation_task.py`, `web/tasks/shorts_creation_task.py`)

- Принимать `file_info` или `sub_task_name` с уникальным именем
- После каждого обновления подзадачи синхронизировать статус в `artifacts.ai_clips_files[file_index].sub_tasks`

### 5. Функция синхронизации статусов (`web/tasks/task_manager.py`)

- Создать метод `sync_subtask_to_file_info(task_id, sub_task_name, file_info_path)` 
- Находит соответствующий файл в artifacts по имени подзадачи
- Обновляет статус подзадачи в метаданных файла

### 6. Отображение раскрывающегося блока в карточке (`web/templates/tasks.html`)

- Добавить кнопку/иконку для раскрытия/сворачивания блока подзадач
- Показывать статусы: clipping, compilation, shorts_creation
- Для каждой подзадачи: статус, прогресс, сообщение, ошибки (если есть)
- Показывать ссылки на выходные файлы из outputs

### 7. Обновление обработчиков кнопок (`web/templates/tasks.html`)

- При нажатии "Компиляция"/"Клипы" передавать `file_info` или доставать его из artifacts по file_path
- Использовать для генерации уникального имени подзадачи

### 8. CSS стили для раскрывающегося блока (`web/templates/tasks.html`)

- Стили для кнопки раскрытия/сворачивания
- Анимация раскрытия
- Стили для отображения статусов подзадач внутри карточки

### To-dos

- [ ] Расширить структуру file_info - добавить поле sub_tasks при создании файла
- [ ] Создать функцию generate_subtask_name для генерации уникальных имен подзадач
- [ ] Обновить create_clips_from_ai для работы с привязанными подзадачами
- [ ] Обновить create_compilation для работы с привязанными подзадачами
- [ ] Создать функцию синхронизации статусов подзадач в artifacts
- [ ] Обновить функции создания подзадач для синхронизации статусов
- [ ] Добавить раскрывающийся блок с подзадачами в карточки
- [ ] Добавить CSS стили для раскрывающегося блока и статусов