-- Initial-release application tables.
-- Supabase Auth owns passwords/accounts; Storage owns audio files.

create table if not exists public.profiles (
    doctor_id uuid primary key references auth.users (id) on delete cascade,
    name text not null default '',
    email text not null default '',
    clinic_name text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.consultations
    add column if not exists patient_id text,
    add column if not exists patient_name text;

create table if not exists public.transcript_segments (
    segment_id text primary key,
    consultation_id text not null references public.consultations (consultation_id) on delete cascade,
    speaker_id text not null,
    speaker_role text not null default 'unknown'
        check (speaker_role in ('doctor', 'patient', 'relative', 'nurse', 'unknown')),
    start_ms integer not null check (start_ms >= 0),
    end_ms integer not null check (end_ms >= start_ms),
    original_text text not null default '',
    english_text text,
    edited_text text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists transcript_segments_consultation_idx
    on public.transcript_segments (consultation_id, start_ms);

create table if not exists public.opd_notes (
    consultation_id text primary key references public.consultations (consultation_id) on delete cascade,
    chief_complaint text not null default '',
    history text not null default '',
    examination text not null default '',
    assessment text not null default '',
    plan text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create or replace function public.set_initial_release_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_initial_release_updated_at();

drop trigger if exists transcript_segments_set_updated_at on public.transcript_segments;
create trigger transcript_segments_set_updated_at
before update on public.transcript_segments
for each row execute function public.set_initial_release_updated_at();

drop trigger if exists opd_notes_set_updated_at on public.opd_notes;
create trigger opd_notes_set_updated_at
before update on public.opd_notes
for each row execute function public.set_initial_release_updated_at();

alter table public.profiles enable row level security;
alter table public.transcript_segments enable row level security;
alter table public.opd_notes enable row level security;

grant select, insert, update, delete on public.profiles to authenticated;
grant delete on public.consultations to authenticated;
grant select, insert, update, delete on public.transcript_segments to authenticated;
grant select, insert, update, delete on public.opd_notes to authenticated;

drop policy if exists "Doctors can manage own profile" on public.profiles;
create policy "Doctors can manage own profile"
on public.profiles for all
to authenticated
using ((select auth.uid()) = doctor_id)
with check ((select auth.uid()) = doctor_id);

drop policy if exists "Doctors can delete own consultations" on public.consultations;
create policy "Doctors can delete own consultations"
on public.consultations for delete
to authenticated
using ((select auth.uid()) = doctor_id);

drop policy if exists "Doctors can manage own transcript segments" on public.transcript_segments;
create policy "Doctors can manage own transcript segments"
on public.transcript_segments for all
to authenticated
using (
    exists (
        select 1 from public.consultations c
        where c.consultation_id = transcript_segments.consultation_id
          and c.doctor_id = (select auth.uid())
    )
)
with check (
    exists (
        select 1 from public.consultations c
        where c.consultation_id = transcript_segments.consultation_id
          and c.doctor_id = (select auth.uid())
    )
);

drop policy if exists "Doctors can manage own opd notes" on public.opd_notes;
create policy "Doctors can manage own opd notes"
on public.opd_notes for all
to authenticated
using (
    exists (
        select 1 from public.consultations c
        where c.consultation_id = opd_notes.consultation_id
          and c.doctor_id = (select auth.uid())
    )
)
with check (
    exists (
        select 1 from public.consultations c
        where c.consultation_id = opd_notes.consultation_id
          and c.doctor_id = (select auth.uid())
    )
);
