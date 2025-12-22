-- Migration: 011_create_views.sql
-- Description: Helper views for simplified querying and reporting
-- Created: 2025-12-19

-- View: v_client_full_inventory
-- One query to see everything about a client across all platforms
CREATE OR REPLACE VIEW v_client_full_inventory AS
SELECT
    -- Client core data
    c.id AS client_id,
    c.client_slug,
    c.client_name,
    c.status,
    c.health_status,
    c.last_health_check_at,
    c.subscription_tier,
    c.website_type,
    c.contact_email,
    c.tags,

    -- GitHub
    c.github_repo,
    gi.resource_url AS github_url,
    gi.resource_metadata->>'last_commit_sha' AS github_last_commit,

    -- Vercel
    c.vercel_project_id,
    c.staging_url AS vercel_staging_url,
    vi.resource_url AS vercel_project_url,
    vi.resource_metadata->>'deployment_state' AS vercel_deployment_state,

    -- Builder.io
    c.builder_space_id,
    bi.resource_url AS builder_space_url,
    bi.resource_metadata->>'content_count' AS builder_content_count,

    -- GCS
    gcsi.resource_metadata->>'latest_backup_at' AS gcs_latest_backup_at,
    gcsi.resource_metadata->>'backup_count' AS gcs_backup_count,

    -- Latest deployment
    (
        SELECT sd.deployed_at
        FROM site_deployments sd
        WHERE sd.client_id = c.id
        AND sd.status = 'success'
        AND sd.rolled_back = FALSE
        ORDER BY sd.deployed_at DESC
        LIMIT 1
    ) AS latest_deployment_at,

    -- Latest health check
    (
        SELECT h.overall_status
        FROM site_health_checks h
        WHERE h.client_id = c.id
        ORDER BY h.checked_at DESC
        LIMIT 1
    ) AS latest_health_status,

    -- Timestamps
    c.created_at,
    c.updated_at

FROM clients c

-- Join with platform inventory
LEFT JOIN platform_inventory gi ON c.id = gi.client_id AND gi.platform = 'github'
LEFT JOIN platform_inventory vi ON c.id = vi.client_id AND vi.platform = 'vercel'
LEFT JOIN platform_inventory bi ON c.id = bi.client_id AND bi.platform = 'builder'
LEFT JOIN platform_inventory gcsi ON c.id = gcsi.client_id AND gcsi.platform = 'gcs'

WHERE c.deletion_scheduled_at IS NULL; -- Exclude soft-deleted clients

COMMENT ON VIEW v_client_full_inventory IS 'Complete client view with all platform resources - primary view for DARX queries';


-- View: v_orphaned_resources
-- Resources that exist in platforms but have no matching client
CREATE OR REPLACE VIEW v_orphaned_resources AS
SELECT
    pi.id,
    pi.platform,
    pi.resource_type,
    pi.resource_name,
    pi.resource_id,
    pi.resource_url,
    pi.discovered_at,
    pi.last_verified_at,
    pi.resource_metadata,

    -- Calculate age in days
    EXTRACT(DAY FROM (NOW() - pi.discovered_at)) AS orphaned_days,

    -- Verification freshness
    EXTRACT(HOUR FROM (NOW() - pi.last_verified_at)) AS hours_since_verified

FROM platform_inventory pi

WHERE pi.is_orphaned = TRUE
AND pi.is_drift = FALSE

ORDER BY pi.discovered_at DESC;

COMMENT ON VIEW v_orphaned_resources IS 'Platform resources with no matching client - candidates for cleanup';


-- View: v_sites_pending_deletion
-- Sites in soft-delete state awaiting recovery or permanent deletion
CREATE OR REPLACE VIEW v_sites_pending_deletion AS
SELECT
    ds.id,
    ds.original_client_id,
    ds.client_data->>'client_slug' AS client_slug,
    ds.client_data->>'client_name' AS client_name,
    ds.deleted_at,
    ds.deleted_by,
    ds.deletion_reason,
    ds.recovery_deadline,

    -- Calculate days until permanent deletion
    EXTRACT(DAY FROM (ds.recovery_deadline - NOW())) AS days_until_permanent_deletion,

    -- Platform deletion progress
    ds.github_deleted,
    ds.vercel_deleted,
    ds.builder_deleted,
    ds.gcs_deleted,

    -- Calculate overall deletion progress
    (
        (CASE WHEN ds.github_deleted THEN 1 ELSE 0 END +
         CASE WHEN ds.vercel_deleted THEN 1 ELSE 0 END +
         CASE WHEN ds.builder_deleted THEN 1 ELSE 0 END +
         CASE WHEN ds.gcs_deleted THEN 1 ELSE 0 END)::FLOAT / 4.0 * 100
    ) AS deletion_progress_percent,

    -- Recovery status
    ds.recovered,
    ds.recovered_at,
    ds.new_client_id,

    -- Permanent deletion
    ds.permanently_deleted,
    ds.permanently_deleted_at

FROM deleted_sites ds

WHERE ds.permanently_deleted = FALSE

ORDER BY ds.recovery_deadline ASC;

COMMENT ON VIEW v_sites_pending_deletion IS 'Soft-deleted sites with recovery window tracking';


-- View: v_deployment_history
-- Recent deployment history across all clients
CREATE OR REPLACE VIEW v_deployment_history AS
SELECT
    sd.id AS deployment_id,
    c.client_slug,
    c.client_name,
    sd.deployed_at,
    sd.deployed_by,
    sd.deployment_trigger,
    sd.status,
    sd.build_state,
    sd.commit_sha,
    sd.vercel_deployment_id,
    sd.staging_url,
    sd.rolled_back,

    -- Calculate deployment age
    EXTRACT(HOUR FROM (NOW() - sd.deployed_at)) AS hours_ago

FROM site_deployments sd
JOIN clients c ON sd.client_id = c.id

ORDER BY sd.deployed_at DESC;

COMMENT ON VIEW v_deployment_history IS 'Complete deployment timeline for all clients';


-- View: v_health_summary
-- Current health status across all clients
CREATE OR REPLACE VIEW v_health_summary AS
SELECT
    c.client_slug,
    c.client_name,
    c.health_status,
    c.last_health_check_at,

    -- Latest health check details
    lh.github_status,
    lh.vercel_status,
    lh.builder_status,
    lh.gcs_status,
    lh.staging_url_status,

    -- Calculate staleness
    EXTRACT(HOUR FROM (NOW() - c.last_health_check_at)) AS hours_since_check,

    CASE
        WHEN c.last_health_check_at IS NULL THEN 'never_checked'
        WHEN NOW() - c.last_health_check_at > INTERVAL '24 hours' THEN 'stale'
        WHEN NOW() - c.last_health_check_at > INTERVAL '6 hours' THEN 'aging'
        ELSE 'fresh'
    END AS check_freshness

FROM clients c

LEFT JOIN LATERAL (
    SELECT *
    FROM site_health_checks h
    WHERE h.client_id = c.id
    ORDER BY h.checked_at DESC
    LIMIT 1
) lh ON TRUE

WHERE c.deletion_scheduled_at IS NULL

ORDER BY
    CASE c.health_status
        WHEN 'down' THEN 1
        WHEN 'degraded' THEN 2
        WHEN 'unknown' THEN 3
        WHEN 'healthy' THEN 4
    END,
    c.last_health_check_at ASC NULLS FIRST;

COMMENT ON VIEW v_health_summary IS 'Current health overview for all active clients';


-- View: v_recent_operations
-- Recent operations across all clients for monitoring
CREATE OR REPLACE VIEW v_recent_operations AS
SELECT
    rol.id AS operation_id,
    rol.client_slug,
    rol.operation_type,
    rol.operation_status,
    rol.started_at,
    rol.completed_at,
    rol.duration_ms,
    rol.initiated_by,
    rol.trigger_source,
    rol.success_count,
    rol.failure_count,

    -- Platform success breakdown
    CASE WHEN rol.github_result->>'success' = 'true' THEN 'success' ELSE 'failed' END AS github_status,
    CASE WHEN rol.vercel_result->>'success' = 'true' THEN 'success' ELSE 'failed' END AS vercel_status,
    CASE WHEN rol.builder_result->>'success' = 'true' THEN 'success' ELSE 'failed' END AS builder_status,
    CASE WHEN rol.gcs_result->>'success' = 'true' THEN 'success' ELSE 'failed' END AS gcs_status,

    -- Error summary
    array_length(rol.error_messages, 1) AS error_count

FROM registry_operations_log rol

ORDER BY rol.started_at DESC

LIMIT 100;

COMMENT ON VIEW v_recent_operations IS 'Recent operations across all platforms for monitoring and debugging';
