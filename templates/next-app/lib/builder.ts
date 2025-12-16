import { builder } from '@builder.io/react';
import { headers } from 'next/headers';

builder.init(process.env.NEXT_PUBLIC_BUILDER_API_KEY!);

/**
 * Get client slug from request headers (set by middleware)
 */
export function getClientSlug(): string {
  const headersList = headers();
  const clientSlug = headersList.get('x-client-slug');

  if (!clientSlug) {
    throw new Error('Client slug not found in request headers');
  }

  return clientSlug;
}

/**
 * Fetch Builder.io content with automatic client_slug scoping
 *
 * IMPORTANT: This function enforces multi-tenant security by automatically
 * filtering content by clientSlug for shared Builder.io spaces.
 *
 * @param model - Builder.io model name (client-page, client-section, client-symbol for shared spaces)
 * @param urlPath - Page URL path (e.g., '/', '/about', '/contact')
 * @param env - Environment tier (entry, staging, production)
 * @returns Builder.io content entry or null
 */
export async function fetchBuilderContent(
  model: string,
  urlPath: string,
  env: string = 'entry'
) {
  const clientSlug = getClientSlug();
  const spaceMode = process.env.BUILDER_SPACE_MODE || 'DEDICATED';

  // For shared spaces, use client-page model and filter by clientSlug
  if (spaceMode === 'SHARED') {
    const content = await builder
      .get(model, {
        query: {
          // IMPORTANT: Builder.io uses camelCase field names (clientSlug, not client_slug)
          'data.clientSlug': clientSlug,
          'data.urlPath': urlPath,
          'data.env': env
        }
      })
      .promise();

    // SECURITY: Verify response matches expected clientSlug
    if (content?.data?.clientSlug !== clientSlug) {
      throw new Error(`Security violation: slug mismatch (expected ${clientSlug}, got ${content?.data?.clientSlug})`);
    }

    return content;
  } else {
    // Dedicated space uses traditional URL matching
    return await builder
      .get(model, {
        url: urlPath
      })
      .promise();
  }
}

/**
 * Fetch all content entries for current client
 *
 * @param model - Builder.io model name
 * @param env - Environment tier (entry, staging, production)
 * @param limit - Maximum number of entries to return
 * @returns Array of Builder.io content entries
 */
export async function fetchAllClientContent(
  model: string,
  env: string = 'entry',
  limit: number = 100
) {
  const clientSlug = getClientSlug();
  const spaceMode = process.env.BUILDER_SPACE_MODE || 'DEDICATED';

  if (spaceMode === 'SHARED') {
    const content = await builder
      .getAll(model, {
        query: {
          // IMPORTANT: Builder.io uses camelCase field names (clientSlug, not client_slug)
          'data.clientSlug': clientSlug,
          'data.env': env
        },
        limit
      });

    // SECURITY: Verify all responses match expected clientSlug
    const invalidEntries = content.filter(
      entry => entry.data?.clientSlug !== clientSlug
    );

    if (invalidEntries.length > 0) {
      throw new Error(`Security violation: Found ${invalidEntries.length} entries with mismatched clientSlug`);
    }

    return content;
  } else {
    // Dedicated space returns all content without filtering
    return await builder.getAll(model, { limit });
  }
}
