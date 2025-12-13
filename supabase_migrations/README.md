# Supabase Migrations

This directory contains SQL migration files for the DARX Site Generator Supabase database.

## Applying Migrations

### Option 1: Supabase Dashboard (Recommended)
1. Go to your Supabase project dashboard
2. Navigate to the SQL Editor
3. Copy the contents of `create_site_generations_table.sql`
4. Paste and run the SQL

### Option 2: Supabase CLI
```bash
# Install Supabase CLI if not already installed
npm install -g supabase

# Link to your project
supabase link --project-ref YOUR_PROJECT_REF

# Run the migration
supabase db push --migrations-file supabase_migrations/create_site_generations_table.sql
```

### Option 3: Direct SQL Execution
```bash
# Using psql (requires direct database access)
psql -h YOUR_SUPABASE_HOST -U postgres -d postgres -f supabase_migrations/create_site_generations_table.sql
```

## Migrations

### create_site_generations_table.sql
Creates the `darx_site_generations` table for tracking website generation attempts and build results.

**Table Schema:**
- `id`: Auto-incrementing primary key
- `created_at`: Timestamp of generation attempt
- `project_name`: Name of the generated project
- `industry`: Industry type (real-estate, saas, etc.)
- `components_generated`: Number of React components
- `files_generated`: Total number of files
- `generation_time_seconds`: Time taken in seconds
- `success`: Whether generation succeeded
- `error_message`: Error details if failed
- `deployment_url`: Vercel staging URL if deployed
- `build_state`: Vercel build state (READY, ERROR, etc.)
- `build_logs`: Build error logs if build failed

**Indexes:**
- `project_name` for fast lookups
- `created_at` for time-based queries
- `success` for filtering failures

**Security:**
- Row Level Security (RLS) enabled
- Service role has full access
- Requires SUPABASE_KEY environment variable
