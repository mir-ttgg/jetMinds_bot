-- Файл инициализации PostgreSQL
-- Создание таблиц при первом запуске контейнера

-- Таблица users
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(100),
    registered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    survey_completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Ответы на вопросы
    ans_1 VARCHAR(100),
    ans_2 VARCHAR(100),
    ans_3 VARCHAR(100),
    ans_4 VARCHAR(100),
    ans_5 VARCHAR(100),
    ans_6 VARCHAR(100),
    ans_7 VARCHAR(100),
    ans_8 TEXT,
    ans_9 VARCHAR(100),
    
    -- Статусы
    qual BOOLEAN DEFAULT FALSE,
    survey_completed BOOLEAN DEFAULT FALSE,
    
    -- Контакты
    phone VARCHAR(20),
    comments TEXT,
    
    -- Напоминания
    reminder_10min_sent BOOLEAN DEFAULT FALSE,
    reminder_2h_sent BOOLEAN DEFAULT FALSE,
    reminder_24h_sent BOOLEAN DEFAULT FALSE
);

-- Индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_users_qual ON users(qual);
CREATE INDEX IF NOT EXISTS idx_users_survey_completed ON users(survey_completed);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(registered_at);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone) WHERE phone IS NOT NULL;

-- Комментарии к таблице
COMMENT ON TABLE users IS 'Пользователи Telegram бота';
COMMENT ON COLUMN users.qual IS 'Квалификация пользователя (true/false)';
COMMENT ON COLUMN users.survey_completed IS 'Завершил ли пользователь опрос';

-- Проверяем создание таблицы
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users') THEN
        RAISE NOTICE '✅ Таблица users успешно создана';
    ELSE
        RAISE EXCEPTION '❌ Таблица users не создана';
    END IF;
END $$;