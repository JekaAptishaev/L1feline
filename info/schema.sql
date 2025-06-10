--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5
-- Dumped by pg_dump version 17.5

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: adminaccesscodes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.adminaccesscodes (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    code character varying(64) NOT NULL,
    is_one_time boolean DEFAULT true NOT NULL,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);


ALTER TABLE public.adminaccesscodes OWNER TO postgres;

--
-- Name: changelog; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.changelog (
    id bigint NOT NULL,
    user_id bigint,
    action_type character varying(50) NOT NULL,
    details jsonb,
    entity_type character varying(50),
    entity_id character varying(255),
    changed_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.changelog OWNER TO postgres;

--
-- Name: changelog_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.changelog_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.changelog_id_seq OWNER TO postgres;

--
-- Name: changelog_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.changelog_id_seq OWNED BY public.changelog.id;


--
-- Name: deadlines; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.deadlines (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    event_id uuid NOT NULL,
    description text,
    deadline_at timestamp with time zone NOT NULL
);


ALTER TABLE public.deadlines OWNER TO postgres;

--
-- Name: events; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.events (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    group_id uuid NOT NULL,
    created_by_user_id bigint NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    subject character varying(255),
    date date NOT NULL,
    is_important boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.events OWNER TO postgres;

--
-- Name: groupinvitations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.groupinvitations (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    group_id uuid NOT NULL,
    invited_by_user_id bigint NOT NULL,
    invite_token character varying(36) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    is_used boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.groupinvitations OWNER TO postgres;

--
-- Name: groupmembers; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.groupmembers (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id bigint NOT NULL,
    group_id uuid NOT NULL,
    is_leader boolean DEFAULT false NOT NULL,
    is_assistant boolean DEFAULT false NOT NULL,
    joined_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.groupmembers OWNER TO postgres;

--
-- Name: groups; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.groups (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    creator_id bigint
);


ALTER TABLE public.groups OWNER TO postgres;

--
-- Name: queueparticipants; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.queueparticipants (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    queue_id uuid NOT NULL,
    user_id bigint NOT NULL,
    "position" integer NOT NULL,
    joined_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.queueparticipants OWNER TO postgres;

--
-- Name: queues; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.queues (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    event_id uuid NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    max_participants integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.queues OWNER TO postgres;

--
-- Name: topiclists; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.topiclists (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    event_id uuid NOT NULL,
    title character varying(255) NOT NULL,
    max_participants_per_topic integer NOT NULL,
    created_by_user_id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.topiclists OWNER TO postgres;

--
-- Name: topics; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.topics (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    topic_list_id uuid NOT NULL,
    title character varying(255) NOT NULL,
    description text
);


ALTER TABLE public.topics OWNER TO postgres;

--
-- Name: topicselections; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.topicselections (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    topic_id uuid NOT NULL,
    user_id bigint NOT NULL,
    selected_at timestamp with time zone DEFAULT now() NOT NULL,
    is_confirmed boolean DEFAULT false NOT NULL,
    confirmed_by_user_id bigint
);


ALTER TABLE public.topicselections OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    telegram_id bigint NOT NULL,
    telegram_username character varying(255),
    first_name character varying(255) NOT NULL,
    last_name character varying(255),
    middle_name character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_active_at timestamp with time zone DEFAULT now() NOT NULL,
    notification_settings jsonb
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: viewedevents; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.viewedevents (
    user_id bigint NOT NULL,
    event_id uuid NOT NULL,
    viewed_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.viewedevents OWNER TO postgres;

--
-- Name: changelog id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.changelog ALTER COLUMN id SET DEFAULT nextval('public.changelog_id_seq'::regclass);


--
-- Name: adminaccesscodes adminaccesscodes_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.adminaccesscodes
    ADD CONSTRAINT adminaccesscodes_code_key UNIQUE (code);


--
-- Name: adminaccesscodes adminaccesscodes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.adminaccesscodes
    ADD CONSTRAINT adminaccesscodes_pkey PRIMARY KEY (id);


--
-- Name: changelog changelog_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.changelog
    ADD CONSTRAINT changelog_pkey PRIMARY KEY (id);


--
-- Name: deadlines deadlines_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.deadlines
    ADD CONSTRAINT deadlines_pkey PRIMARY KEY (id);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);


--
-- Name: groupinvitations groupinvitations_invite_token_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.groupinvitations
    ADD CONSTRAINT groupinvitations_invite_token_key UNIQUE (invite_token);


--
-- Name: groupinvitations groupinvitations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.groupinvitations
    ADD CONSTRAINT groupinvitations_pkey PRIMARY KEY (id);


--
-- Name: groupmembers groupmembers_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.groupmembers
    ADD CONSTRAINT groupmembers_pkey PRIMARY KEY (id);


--
-- Name: groupmembers groupmembers_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.groupmembers
    ADD CONSTRAINT groupmembers_user_id_key UNIQUE (user_id);


--
-- Name: groups groups_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_pkey PRIMARY KEY (id);


--
-- Name: queueparticipants queueparticipants_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.queueparticipants
    ADD CONSTRAINT queueparticipants_pkey PRIMARY KEY (id);


--
-- Name: queueparticipants queueparticipants_queue_id_position_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.queueparticipants
    ADD CONSTRAINT queueparticipants_queue_id_position_key UNIQUE (queue_id, "position");


--
-- Name: queueparticipants queueparticipants_queue_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.queueparticipants
    ADD CONSTRAINT queueparticipants_queue_id_user_id_key UNIQUE (queue_id, user_id);


--
-- Name: queues queues_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.queues
    ADD CONSTRAINT queues_pkey PRIMARY KEY (id);


--
-- Name: topiclists topiclists_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.topiclists
    ADD CONSTRAINT topiclists_pkey PRIMARY KEY (id);


--
-- Name: topics topics_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.topics
    ADD CONSTRAINT topics_pkey PRIMARY KEY (id);


--
-- Name: topicselections topicselections_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.topicselections
    ADD CONSTRAINT topicselections_pkey PRIMARY KEY (id);


--
-- Name: topicselections topicselections_topic_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.topicselections
    ADD CONSTRAINT topicselections_topic_id_user_id_key UNIQUE (topic_id, user_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (telegram_id);


--
-- Name: viewedevents viewedevents_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.viewedevents
    ADD CONSTRAINT viewedevents_pkey PRIMARY KEY (user_id, event_id);


--
-- Name: idx_events_group_id_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_events_group_id_date ON public.events USING btree (group_id, date);


--
-- Name: idx_groupinvitations_token; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_groupinvitations_token ON public.groupinvitations USING btree (invite_token);


--
-- Name: idx_groupmembers_group_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_groupmembers_group_id ON public.groupmembers USING btree (group_id);


--
-- Name: changelog changelog_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.changelog
    ADD CONSTRAINT changelog_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(telegram_id) ON DELETE SET NULL;


--
-- Name: deadlines deadlines_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.deadlines
    ADD CONSTRAINT deadlines_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE CASCADE;


--
-- Name: events events_created_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_created_by_user_id_fkey FOREIGN KEY (created_by_user_id) REFERENCES public.users(telegram_id) ON DELETE SET NULL;


--
-- Name: events events_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE CASCADE;


--
-- Name: groupinvitations groupinvitations_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.groupinvitations
    ADD CONSTRAINT groupinvitations_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE CASCADE;


--
-- Name: groupinvitations groupinvitations_invited_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.groupinvitations
    ADD CONSTRAINT groupinvitations_invited_by_user_id_fkey FOREIGN KEY (invited_by_user_id) REFERENCES public.users(telegram_id) ON DELETE CASCADE;


--
-- Name: groupmembers groupmembers_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.groupmembers
    ADD CONSTRAINT groupmembers_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE CASCADE;


--
-- Name: groupmembers groupmembers_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.groupmembers
    ADD CONSTRAINT groupmembers_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(telegram_id) ON DELETE CASCADE;


--
-- Name: groups groups_creator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_creator_id_fkey FOREIGN KEY (creator_id) REFERENCES public.users(telegram_id) ON DELETE SET NULL;


--
-- Name: queueparticipants queueparticipants_queue_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.queueparticipants
    ADD CONSTRAINT queueparticipants_queue_id_fkey FOREIGN KEY (queue_id) REFERENCES public.queues(id) ON DELETE CASCADE;


--
-- Name: queueparticipants queueparticipants_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.queueparticipants
    ADD CONSTRAINT queueparticipants_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(telegram_id) ON DELETE CASCADE;


--
-- Name: queues queues_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.queues
    ADD CONSTRAINT queues_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE CASCADE;


--
-- Name: topiclists topiclists_created_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.topiclists
    ADD CONSTRAINT topiclists_created_by_user_id_fkey FOREIGN KEY (created_by_user_id) REFERENCES public.users(telegram_id) ON DELETE SET NULL;


--
-- Name: topiclists topiclists_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.topiclists
    ADD CONSTRAINT topiclists_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE CASCADE;


--
-- Name: topics topics_topic_list_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.topics
    ADD CONSTRAINT topics_topic_list_id_fkey FOREIGN KEY (topic_list_id) REFERENCES public.topiclists(id) ON DELETE CASCADE;


--
-- Name: topicselections topicselections_confirmed_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.topicselections
    ADD CONSTRAINT topicselections_confirmed_by_user_id_fkey FOREIGN KEY (confirmed_by_user_id) REFERENCES public.users(telegram_id) ON DELETE SET NULL;


--
-- Name: topicselections topicselections_topic_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.topicselections
    ADD CONSTRAINT topicselections_topic_id_fkey FOREIGN KEY (topic_id) REFERENCES public.topics(id) ON DELETE CASCADE;


--
-- Name: topicselections topicselections_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.topicselections
    ADD CONSTRAINT topicselections_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(telegram_id) ON DELETE CASCADE;


--
-- Name: viewedevents viewedevents_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.viewedevents
    ADD CONSTRAINT viewedevents_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE CASCADE;


--
-- Name: viewedevents viewedevents_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.viewedevents
    ADD CONSTRAINT viewedevents_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(telegram_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--
