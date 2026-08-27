-- Base consultation table and private audio bucket.

create table if not exists public.consultations (
    consultation_id text primary key,
    doctor_id uuid not null references auth.users (id) on delete cascade,
    patient_id text,
    patient_name text,
    status text not null default 'processing'
        check (status in ('processing', 'ready_for_review', 'failed')),
    audio_path text,
    audio_mime_type text
        check (audio_mime_type is null or audio_mime_type in ('audio/mpeg', 'audio/wav', 'audio/mp4')),
    error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists consultations_doctor_id_idx
    on public.consultations (doctor_id);
create index if not exists consultations_created_at_idx
    on public.consultations (created_at desc);

create or replace function public.set_consultations_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists consultations_set_updated_at on public.consultations;
create trigger consultations_set_updated_at
before update on public.consultations
for each row execute function public.set_consultations_updated_at();

alter table public.consultations enable row level security;

grant select, insert, update, delete on public.consultations to authenticated;

drop policy if exists "Doctors can manage own consultations" on public.consultations;
create policy "Doctors can manage own consultations"
on public.consultations for all
to authenticated
using ((select auth.uid()) = doctor_id)
with check ((select auth.uid()) = doctor_id);

insert into storage.buckets (
    id, name, public, file_size_limit, allowed_mime_types
)
values (
    'consultation-audio',
    'consultation-audio',
    false,
    52428800,
    array['audio/mpeg', 'audio/wav', 'audio/mp4']
)
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "Doctors can upload own consultation audio" on storage.objects;
create policy "Doctors can upload own consultation audio"
on storage.objects for insert
to authenticated
with check (
    bucket_id = 'consultation-audio'
    and (storage.foldername(name))[1] = (select auth.uid())::text
);

drop policy if exists "Doctors can read own consultation audio" on storage.objects;
create policy "Doctors can read own consultation audio"
on storage.objects for select
to authenticated
using (
    bucket_id = 'consultation-audio'
    and (storage.foldername(name))[1] = (select auth.uid())::text
);

drop policy if exists "Doctors can delete own consultation audio" on storage.objects;
create policy "Doctors can delete own consultation audio"
on storage.objects for delete
to authenticated
using (
    bucket_id = 'consultation-audio'
    and (storage.foldername(name))[1] = (select auth.uid())::text
);
