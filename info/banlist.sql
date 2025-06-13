CREATE TABLE public.banlist (
    id UUID DEFAULT public.uuid_generate_v4() PRIMARY KEY,
    group_id UUID NOT NULL,
    user_id BIGINT NOT NULL,
    banned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reason TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES public.users(telegram_id) ON DELETE CASCADE
);