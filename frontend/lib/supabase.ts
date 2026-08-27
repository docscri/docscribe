import { createClient } from '@supabase/supabase-js';

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

export const supabase = url && key ? createClient(url, key) : null;
export const apiUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? '';
const missingConfiguration = [!url && 'NEXT_PUBLIC_SUPABASE_URL', !key && 'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY', !apiUrl && 'NEXT_PUBLIC_API_URL'].filter(Boolean);
export const configurationError = missingConfiguration.length ? `Missing configuration: ${missingConfiguration.join(', ')}` : '';
