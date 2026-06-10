<?php
/**
 * Plugin Name: PracticeRank SEO
 * Plugin URI: https://practicerank.ai
 * Description: Full SEO/AEO integration — JSON-LD schema injection, llms.txt serving, content publishing via REST API, and AI-optimized robots.txt.
 * Version: 2.0
 * Author: PracticeRank
 * Author URI: https://practicerank.ai
 * License: Proprietary
 * Requires at least: 5.6
 * Tested up to: 6.7
 * Requires PHP: 7.4
 */

// Prevent direct access
if (!defined('ABSPATH')) exit;

define('PRACTICERANK_VERSION', '2.0');
define('PRACTICERANK_OPTION_PREFIX', 'practicerank_');

// Minimum requirements
define('PRACTICERANK_MIN_WP', '5.6');
define('PRACTICERANK_MIN_PHP', '7.4');

// Polyfill str_starts_with for PHP < 8.0
if (!function_exists('str_starts_with')) {
    function str_starts_with($haystack, $needle) {
        return strncmp($haystack, $needle, strlen($needle)) === 0;
    }
}

// ─── Activation / Deactivation ──────────────────────────────────────────────

register_activation_hook(__FILE__, 'practicerank_activate');
register_deactivation_hook(__FILE__, 'practicerank_deactivate');

function practicerank_activate() {
    // Check WordPress version
    global $wp_version;
    if (version_compare($wp_version, PRACTICERANK_MIN_WP, '<')) {
        deactivate_plugins(plugin_basename(__FILE__));
        wp_die(
            sprintf('PracticeRank SEO requires WordPress %s or higher. You are running %s.', PRACTICERANK_MIN_WP, $wp_version),
            'Plugin Activation Error',
            ['back_link' => true]
        );
    }

    // Check PHP version
    if (version_compare(PHP_VERSION, PRACTICERANK_MIN_PHP, '<')) {
        deactivate_plugins(plugin_basename(__FILE__));
        wp_die(
            sprintf('PracticeRank SEO requires PHP %s or higher. You are running %s.', PRACTICERANK_MIN_PHP, PHP_VERSION),
            'Plugin Activation Error',
            ['back_link' => true]
        );
    }

    $upload_dir = wp_upload_dir();
    $pr_dir = $upload_dir['basedir'] . '/practicerank';
    if (!file_exists($pr_dir)) {
        wp_mkdir_p($pr_dir);
    }

    // Protect uploads directory from direct browsing
    $htaccess = $pr_dir . '/.htaccess';
    if (!file_exists($htaccess)) {
        file_put_contents($htaccess, "Options -Indexes\n");
    }

    // Generate API key on first activation
    if (!get_option(PRACTICERANK_OPTION_PREFIX . 'api_key')) {
        update_option(PRACTICERANK_OPTION_PREFIX . 'api_key', wp_generate_password(40, false));
    }

    // Default settings
    if (get_option(PRACTICERANK_OPTION_PREFIX . 'schema_enabled') === false) {
        update_option(PRACTICERANK_OPTION_PREFIX . 'schema_enabled', '1');
    }
    if (get_option(PRACTICERANK_OPTION_PREFIX . 'robots_enabled') === false) {
        update_option(PRACTICERANK_OPTION_PREFIX . 'robots_enabled', '1');
    }
    if (get_option(PRACTICERANK_OPTION_PREFIX . 'content_as_draft') === false) {
        update_option(PRACTICERANK_OPTION_PREFIX . 'content_as_draft', '1');
    }

    // Rewrite rules
    practicerank_add_rewrite_rules();
    flush_rewrite_rules();
}

function practicerank_deactivate() {
    flush_rewrite_rules();
}

// ─── Rewrite Rules (llms.txt) ───────────────────────────────────────────────

add_action('init', 'practicerank_add_rewrite_rules');

function practicerank_add_rewrite_rules() {
    add_rewrite_rule('^llms\.txt$', 'index.php?practicerank_file=llms.txt', 'top');
    add_rewrite_rule('^llms-full\.txt$', 'index.php?practicerank_file=llms-full.txt', 'top');
}

add_filter('query_vars', function($vars) {
    $vars[] = 'practicerank_file';
    return $vars;
});

add_action('template_redirect', function() {
    $file = get_query_var('practicerank_file');
    if (!$file) return;

    $upload_dir = wp_upload_dir();
    $filepath = $upload_dir['basedir'] . '/practicerank/' . basename($file);

    if (file_exists($filepath)) {
        header('Content-Type: text/plain; charset=utf-8');
        header('Cache-Control: public, max-age=3600');
        header('X-Robots-Tag: noindex');
        header('X-Generated-By: PracticeRank');
        readfile($filepath);
        exit;
    }

    status_header(404);
    echo 'File not found. Connect PracticeRank to generate.';
    exit;
});

// ─── Schema Injection (<head>) ──────────────────────────────────────────────

add_action('wp_head', 'practicerank_inject_schema', 1);

function practicerank_inject_schema() {
    if (get_option(PRACTICERANK_OPTION_PREFIX . 'schema_enabled') !== '1') return;

    $upload_dir = wp_upload_dir();
    $schema_dir = $upload_dir['basedir'] . '/practicerank/schema';

    if (!is_dir($schema_dir)) return;

    // Global schemas (LocalBusiness, Organization) — injected on every page
    $global_file = $schema_dir . '/global.json';
    if (file_exists($global_file)) {
        $schemas = json_decode(file_get_contents($global_file), true);
        if (is_array($schemas)) {
            foreach ($schemas as $schema) {
                echo '<script type="application/ld+json">' . "\n";
                echo wp_json_encode($schema, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
                echo "\n</script>\n";
            }
        }
    }

    // Page-specific schemas — matched by URL path
    if (is_singular()) {
        $post = get_queried_object();
        $slug = $post->post_name;

        // Check for page-specific schema file
        $page_file = $schema_dir . '/page-' . sanitize_file_name($slug) . '.json';
        if (file_exists($page_file)) {
            $schemas = json_decode(file_get_contents($page_file), true);
            if (is_array($schemas)) {
                foreach ($schemas as $schema) {
                    echo '<script type="application/ld+json">' . "\n";
                    echo wp_json_encode($schema, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
                    echo "\n</script>\n";
                }
            }
        }

        // FAQPage schema for posts/pages that have FAQ blocks
        $faq_file = $schema_dir . '/faq-' . sanitize_file_name($slug) . '.json';
        if (file_exists($faq_file)) {
            $schema = json_decode(file_get_contents($faq_file), true);
            if ($schema) {
                echo '<script type="application/ld+json">' . "\n";
                echo wp_json_encode($schema, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
                echo "\n</script>\n";
            }
        }
    }
}

// ─── AI-Optimized Robots.txt ────────────────────────────────────────────────

add_filter('robots_txt', function($output, $public) {
    if (get_option(PRACTICERANK_OPTION_PREFIX . 'robots_enabled') !== '1') return $output;

    $upload_dir = wp_upload_dir();
    $robots_file = $upload_dir['basedir'] . '/practicerank/robots.txt';

    if (file_exists($robots_file)) {
        return file_get_contents($robots_file);
    }

    // Append AI crawler rules to default robots.txt
    $output .= "\n# AI Search Engine Crawlers — PracticeRank\n";
    $ai_bots = [
        'ChatGPT-User', 'GPTBot', 'Google-Extended', 'PerplexityBot',
        'ClaudeBot', 'Applebot-Extended', 'anthropic-ai', 'CCBot',
        'Bytespider', 'cohere-ai',
    ];
    foreach ($ai_bots as $bot) {
        $output .= "User-agent: {$bot}\nAllow: /\n\n";
    }

    // Point to llms.txt
    $site_url = get_site_url();
    $output .= "# LLM discovery files\n";
    $output .= "# llms.txt: {$site_url}/llms.txt\n";
    $output .= "# llms-full.txt: {$site_url}/llms-full.txt\n";

    return $output;
}, 10, 2);

// ─── REST API Endpoints ─────────────────────────────────────────────────────

add_action('rest_api_init', 'practicerank_register_routes');

function practicerank_register_routes() {
    $namespace = 'practicerank/v1';

    // Health check (no auth)
    register_rest_route($namespace, '/health', [
        'methods' => 'GET',
        'callback' => 'practicerank_api_health',
        'permission_callback' => '__return_true',
    ]);

    // Push schema markup
    register_rest_route($namespace, '/schema', [
        'methods' => 'POST',
        'callback' => 'practicerank_api_push_schema',
        'permission_callback' => 'practicerank_check_api_key',
    ]);

    // Push llms.txt / llms-full.txt / robots.txt
    register_rest_route($namespace, '/files', [
        'methods' => 'POST',
        'callback' => 'practicerank_api_push_files',
        'permission_callback' => 'practicerank_check_api_key',
    ]);

    // Push content (blog post, page, FAQ)
    register_rest_route($namespace, '/content', [
        'methods' => 'POST',
        'callback' => 'practicerank_api_push_content',
        'permission_callback' => 'practicerank_check_api_key',
    ]);

    // Update existing content
    register_rest_route($namespace, '/content/(?P<id>\d+)', [
        'methods' => 'PUT',
        'callback' => 'practicerank_api_update_content',
        'permission_callback' => 'practicerank_check_api_key',
    ]);

    // Get site info (pages, posts, categories)
    register_rest_route($namespace, '/site-info', [
        'methods' => 'GET',
        'callback' => 'practicerank_api_site_info',
        'permission_callback' => 'practicerank_check_api_key',
    ]);
}

function practicerank_check_api_key($request) {
    $header = $request->get_header('X-PracticeRank-Key');
    if (!$header) {
        $header = $request->get_header('Authorization');
        if ($header && str_starts_with($header, 'Bearer ')) {
            $header = substr($header, 7);
        }
    }

    $stored_key = get_option(PRACTICERANK_OPTION_PREFIX . 'api_key');
    if (!$stored_key || !$header) {
        return new WP_Error('unauthorized', 'Invalid or missing API key', ['status' => 401]);
    }

    if (!hash_equals($stored_key, $header)) {
        // Log failed auth attempt
        error_log(sprintf(
            'PracticeRank: Failed API auth from %s for %s',
            $_SERVER['REMOTE_ADDR'] ?? 'unknown',
            $request->get_route()
        ));
        return new WP_Error('unauthorized', 'Invalid API key', ['status' => 401]);
    }

    return true;
}

// --- Health Check ---

function practicerank_api_health($request) {
    $upload_dir = wp_upload_dir();
    $pr_dir = $upload_dir['basedir'] . '/practicerank';

    return rest_ensure_response([
        'status' => 'ok',
        'version' => PRACTICERANK_VERSION,
        'site_name' => get_bloginfo('name'),
        'site_url' => get_site_url(),
        'wp_version' => get_bloginfo('version'),
        'schema_enabled' => get_option(PRACTICERANK_OPTION_PREFIX . 'schema_enabled') === '1',
        'has_llms_txt' => file_exists($pr_dir . '/llms.txt'),
        'has_schema' => is_dir($pr_dir . '/schema'),
        'content_as_draft' => get_option(PRACTICERANK_OPTION_PREFIX . 'content_as_draft') === '1',
        'timezone' => wp_timezone_string(),
    ]);
}

// --- Push Schema ---

function practicerank_api_push_schema($request) {
    $body = $request->get_json_params();

    $upload_dir = wp_upload_dir();
    $schema_dir = $upload_dir['basedir'] . '/practicerank/schema';
    if (!file_exists($schema_dir)) {
        wp_mkdir_p($schema_dir);
    }

    $updated = [];

    // Global schemas (LocalBusiness, providers, AggregateRating)
    if (!empty($body['global'])) {
        $schemas = is_array($body['global']) ? $body['global'] : [$body['global']];
        file_put_contents(
            $schema_dir . '/global.json',
            wp_json_encode($schemas, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT)
        );
        $updated[] = 'global';
    }

    // Page-specific schemas (Service, MedicalProcedure)
    if (!empty($body['pages']) && is_array($body['pages'])) {
        foreach ($body['pages'] as $slug => $schemas) {
            $safe_slug = sanitize_file_name($slug);
            $schemas = is_array($schemas) ? $schemas : [$schemas];
            file_put_contents(
                $schema_dir . '/page-' . $safe_slug . '.json',
                wp_json_encode($schemas, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT)
            );
            $updated[] = 'page-' . $safe_slug;
        }
    }

    // FAQ schemas
    if (!empty($body['faqs']) && is_array($body['faqs'])) {
        foreach ($body['faqs'] as $slug => $schema) {
            $safe_slug = sanitize_file_name($slug);
            file_put_contents(
                $schema_dir . '/faq-' . $safe_slug . '.json',
                wp_json_encode($schema, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT)
            );
            $updated[] = 'faq-' . $safe_slug;
        }
    }

    return rest_ensure_response([
        'status' => 'ok',
        'updated' => $updated,
    ]);
}

// --- Push Files (llms.txt, robots.txt) ---

function practicerank_api_push_files($request) {
    $body = $request->get_json_params();

    $upload_dir = wp_upload_dir();
    $pr_dir = $upload_dir['basedir'] . '/practicerank';
    if (!file_exists($pr_dir)) {
        wp_mkdir_p($pr_dir);
    }

    $allowed_files = ['llms.txt', 'llms-full.txt', 'robots.txt'];
    $written = [];

    foreach ($body as $filename => $content) {
        if (!in_array($filename, $allowed_files, true)) continue;
        if (!is_string($content)) continue;

        file_put_contents($pr_dir . '/' . $filename, $content);
        $written[] = $filename;
    }

    // Flush rewrite rules if llms.txt files were updated (ensures routes work)
    if (array_intersect($written, ['llms.txt', 'llms-full.txt'])) {
        flush_rewrite_rules();
    }

    return rest_ensure_response([
        'status' => 'ok',
        'written' => $written,
    ]);
}

// --- Push Content ---

function practicerank_api_push_content($request) {
    $body = $request->get_json_params();

    $type = sanitize_text_field($body['type'] ?? 'post');        // post, page
    $title = sanitize_text_field($body['title'] ?? '');
    $content = $body['content'] ?? '';                            // HTML content
    $slug = sanitize_title($body['slug'] ?? $title);
    $excerpt = sanitize_text_field($body['excerpt'] ?? '');
    $category = sanitize_text_field($body['category'] ?? '');
    $tags = $body['tags'] ?? [];
    $meta_description = sanitize_text_field($body['meta_description'] ?? '');
    $author_name = sanitize_text_field($body['author'] ?? '');
    $featured_image_url = esc_url_raw($body['featured_image_url'] ?? '');
    $faq_schema = $body['faq_schema'] ?? null;
    $page_schema = $body['page_schema'] ?? null;
    $force_publish = !empty($body['publish']);

    if (!$title) {
        return new WP_Error('missing_title', 'Title is required', ['status' => 400]);
    }
    if (!$content) {
        return new WP_Error('missing_content', 'Content is required', ['status' => 400]);
    }

    // Sanitize content — allow standard HTML tags
    $allowed_html = wp_kses_allowed_html('post');
    $content = wp_kses($content, $allowed_html);

    // Determine publish status
    $as_draft = get_option(PRACTICERANK_OPTION_PREFIX . 'content_as_draft') === '1';
    $status = ($as_draft && !$force_publish) ? 'draft' : 'publish';

    // Resolve author
    $author_id = 0;
    if ($author_name) {
        $user = get_user_by('display_name', $author_name);
        if ($user) $author_id = $user->ID;
    }
    if (!$author_id) {
        $author_id = get_current_user_id() ?: 1;  // fallback to admin
    }

    // Check for existing post with same slug to prevent duplicates
    $existing = get_page_by_path($slug, OBJECT, $type === 'page' ? 'page' : 'post');
    if ($existing) {
        return new WP_Error(
            'duplicate_slug',
            "A {$type} with slug '{$slug}' already exists (ID: {$existing->ID}). Use PUT /content/{$existing->ID} to update.",
            ['status' => 409, 'existing_id' => $existing->ID]
        );
    }

    // Create the post/page
    $post_data = [
        'post_title'   => $title,
        'post_content' => $content,
        'post_status'  => $status,
        'post_type'    => $type === 'page' ? 'page' : 'post',
        'post_name'    => $slug,
        'post_excerpt' => $excerpt,
        'post_author'  => $author_id,
        'meta_input'   => [
            '_practicerank_managed' => '1',
            '_practicerank_pushed_at' => current_time('mysql'),
        ],
    ];

    $post_id = wp_insert_post($post_data, true);
    if (is_wp_error($post_id)) {
        return $post_id;
    }

    // Set category
    if ($category && $type !== 'page') {
        $cat_id = practicerank_ensure_category($category);
        wp_set_post_categories($post_id, [$cat_id]);
    }

    // Set tags
    if (!empty($tags) && is_array($tags) && $type !== 'page') {
        wp_set_post_tags($post_id, array_map('sanitize_text_field', $tags));
    }

    // Meta description (Yoast, RankMath, or generic)
    if ($meta_description) {
        practicerank_set_meta_description($post_id, $meta_description);
    }

    // Featured image from URL
    if ($featured_image_url) {
        $thumb_id = practicerank_sideload_image($featured_image_url, $post_id, $title);
        if ($thumb_id && !is_wp_error($thumb_id)) {
            set_post_thumbnail($post_id, $thumb_id);
        }
    }

    // Page-specific schema
    if ($faq_schema || $page_schema) {
        $upload_dir = wp_upload_dir();
        $schema_dir = $upload_dir['basedir'] . '/practicerank/schema';
        if (!file_exists($schema_dir)) wp_mkdir_p($schema_dir);

        if ($faq_schema) {
            file_put_contents(
                $schema_dir . '/faq-' . sanitize_file_name($slug) . '.json',
                wp_json_encode($faq_schema, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT)
            );
        }
        if ($page_schema) {
            $schemas = is_array($page_schema) ? $page_schema : [$page_schema];
            file_put_contents(
                $schema_dir . '/page-' . sanitize_file_name($slug) . '.json',
                wp_json_encode($schemas, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT)
            );
        }
    }

    return rest_ensure_response([
        'status' => 'ok',
        'post_id' => $post_id,
        'post_type' => $type === 'page' ? 'page' : 'post',
        'slug' => $slug,
        'url' => get_permalink($post_id),
        'publish_status' => $status,
    ]);
}

// --- Update Existing Content ---

function practicerank_api_update_content($request) {
    $post_id = (int) $request->get_param('id');
    $body = $request->get_json_params();

    $post = get_post($post_id);
    if (!$post) {
        return new WP_Error('not_found', 'Post not found', ['status' => 404]);
    }

    $update_data = ['ID' => $post_id];

    if (isset($body['title'])) {
        $update_data['post_title'] = sanitize_text_field($body['title']);
    }
    if (isset($body['content'])) {
        $allowed_html = wp_kses_allowed_html('post');
        $update_data['post_content'] = wp_kses($body['content'], $allowed_html);
    }
    if (isset($body['excerpt'])) {
        $update_data['post_excerpt'] = sanitize_text_field($body['excerpt']);
    }
    if (isset($body['status'])) {
        $allowed_statuses = ['draft', 'publish', 'pending', 'private'];
        if (in_array($body['status'], $allowed_statuses, true)) {
            $update_data['post_status'] = $body['status'];
        }
    }

    // Track the update
    $update_data['meta_input'] = [
        '_practicerank_updated_at' => current_time('mysql'),
    ];

    $result = wp_update_post($update_data, true);
    if (is_wp_error($result)) {
        return $result;
    }

    // Update meta description
    if (isset($body['meta_description'])) {
        practicerank_set_meta_description($post_id, sanitize_text_field($body['meta_description']));
    }

    // Update category
    if (isset($body['category']) && $post->post_type === 'post') {
        $cat_id = practicerank_ensure_category(sanitize_text_field($body['category']));
        wp_set_post_categories($post_id, [$cat_id]);
    }

    // Update tags
    if (isset($body['tags']) && is_array($body['tags']) && $post->post_type === 'post') {
        wp_set_post_tags($post_id, array_map('sanitize_text_field', $body['tags']));
    }

    // Update schemas
    $slug = $post->post_name;
    $upload_dir = wp_upload_dir();
    $schema_dir = $upload_dir['basedir'] . '/practicerank/schema';

    if (isset($body['faq_schema'])) {
        if (!file_exists($schema_dir)) wp_mkdir_p($schema_dir);
        file_put_contents(
            $schema_dir . '/faq-' . sanitize_file_name($slug) . '.json',
            wp_json_encode($body['faq_schema'], JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT)
        );
    }
    if (isset($body['page_schema'])) {
        if (!file_exists($schema_dir)) wp_mkdir_p($schema_dir);
        $schemas = is_array($body['page_schema']) ? $body['page_schema'] : [$body['page_schema']];
        file_put_contents(
            $schema_dir . '/page-' . sanitize_file_name($slug) . '.json',
            wp_json_encode($schemas, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT)
        );
    }

    return rest_ensure_response([
        'status' => 'ok',
        'post_id' => $post_id,
        'url' => get_permalink($post_id),
        'publish_status' => get_post_status($post_id),
    ]);
}

// --- Site Info ---

function practicerank_api_site_info($request) {
    // Get all pages
    $pages = get_pages(['sort_column' => 'menu_order']);
    $page_list = [];
    foreach ($pages as $page) {
        $page_list[] = [
            'id' => $page->ID,
            'title' => $page->post_title,
            'slug' => $page->post_name,
            'url' => get_permalink($page->ID),
            'status' => $page->post_status,
            'practicerank_managed' => (bool) get_post_meta($page->ID, '_practicerank_managed', true),
        ];
    }

    // Get recent posts
    $posts = get_posts(['numberposts' => 50, 'post_status' => ['publish', 'draft']]);
    $post_list = [];
    foreach ($posts as $post) {
        $cats = wp_get_post_categories($post->ID, ['fields' => 'names']);
        $post_list[] = [
            'id' => $post->ID,
            'title' => $post->post_title,
            'slug' => $post->post_name,
            'url' => get_permalink($post->ID),
            'status' => $post->post_status,
            'date' => $post->post_date,
            'categories' => $cats,
            'practicerank_managed' => (bool) get_post_meta($post->ID, '_practicerank_managed', true),
        ];
    }

    // Get categories
    $categories = get_categories(['hide_empty' => false]);
    $cat_list = [];
    foreach ($categories as $cat) {
        $cat_list[] = [
            'id' => $cat->term_id,
            'name' => $cat->name,
            'slug' => $cat->slug,
            'count' => $cat->count,
        ];
    }

    // Active theme info
    $theme = wp_get_theme();

    // Detect SEO plugin
    $seo_plugin = 'none';
    if (defined('WPSEO_VERSION')) $seo_plugin = 'yoast';
    elseif (defined('RANK_MATH_VERSION')) $seo_plugin = 'rankmath';
    elseif (defined('AIOSEO_VERSION')) $seo_plugin = 'aioseo';

    return rest_ensure_response([
        'site_name' => get_bloginfo('name'),
        'site_url' => get_site_url(),
        'theme' => $theme->get('Name'),
        'seo_plugin' => $seo_plugin,
        'pages' => $page_list,
        'posts' => $post_list,
        'categories' => $cat_list,
        'practicerank_managed_count' => count(get_posts([
            'numberposts' => -1,
            'post_status' => 'any',
            'meta_key' => '_practicerank_managed',
            'meta_value' => '1',
        ])),
    ]);
}

// ─── Helper Functions ───────────────────────────────────────────────────────

function practicerank_ensure_category($name) {
    $cat = get_cat_ID($name);
    if ($cat) return $cat;

    $result = wp_insert_category([
        'cat_name' => $name,
        'category_nicename' => sanitize_title($name),
    ]);
    return $result ?: 1;
}

function practicerank_set_meta_description($post_id, $description) {
    // Yoast SEO
    if (defined('WPSEO_VERSION')) {
        update_post_meta($post_id, '_yoast_wpseo_metadesc', $description);
        return;
    }
    // RankMath
    if (defined('RANK_MATH_VERSION')) {
        update_post_meta($post_id, 'rank_math_description', $description);
        return;
    }
    // All in One SEO
    if (defined('AIOSEO_VERSION')) {
        update_post_meta($post_id, '_aioseo_description', $description);
        return;
    }
    // Generic fallback — works with most themes
    update_post_meta($post_id, '_practicerank_meta_description', $description);
}

function practicerank_sideload_image($url, $post_id, $description = '') {
    require_once ABSPATH . 'wp-admin/includes/media.php';
    require_once ABSPATH . 'wp-admin/includes/file.php';
    require_once ABSPATH . 'wp-admin/includes/image.php';

    $tmp = download_url($url, 15);
    if (is_wp_error($tmp)) return $tmp;

    $file_array = [
        'name' => basename(wp_parse_url($url, PHP_URL_PATH)) ?: 'image.jpg',
        'tmp_name' => $tmp,
    ];

    $id = media_handle_sideload($file_array, $post_id, $description);

    // Clean up temp file on error
    if (is_wp_error($id)) {
        @unlink($file_array['tmp_name']);
    }

    return $id;
}

// ─── Admin Settings Page ────────────────────────────────────────────────────

add_action('admin_menu', function() {
    add_options_page(
        'PracticeRank SEO',
        'PracticeRank',
        'manage_options',
        'practicerank-seo',
        'practicerank_settings_page'
    );
});

add_action('admin_init', function() {
    // API key is read-only — always return the stored value to prevent tampering
    register_setting('practicerank_settings', PRACTICERANK_OPTION_PREFIX . 'api_key', [
        'sanitize_callback' => function($input) {
            return get_option(PRACTICERANK_OPTION_PREFIX . 'api_key');
        },
    ]);
    register_setting('practicerank_settings', PRACTICERANK_OPTION_PREFIX . 'schema_enabled', [
        'sanitize_callback' => function($input) { return $input === '1' ? '1' : '0'; },
    ]);
    register_setting('practicerank_settings', PRACTICERANK_OPTION_PREFIX . 'robots_enabled', [
        'sanitize_callback' => function($input) { return $input === '1' ? '1' : '0'; },
    ]);
    register_setting('practicerank_settings', PRACTICERANK_OPTION_PREFIX . 'content_as_draft', [
        'sanitize_callback' => function($input) { return $input === '1' ? '1' : '0'; },
    ]);
});

function practicerank_settings_page() {
    $api_key = get_option(PRACTICERANK_OPTION_PREFIX . 'api_key', '');
    $schema_enabled = get_option(PRACTICERANK_OPTION_PREFIX . 'schema_enabled', '1');
    $robots_enabled = get_option(PRACTICERANK_OPTION_PREFIX . 'robots_enabled', '1');
    $content_as_draft = get_option(PRACTICERANK_OPTION_PREFIX . 'content_as_draft', '1');

    $upload_dir = wp_upload_dir();
    $pr_dir = $upload_dir['basedir'] . '/practicerank';
    $has_llms = file_exists($pr_dir . '/llms.txt');
    $has_schema = is_dir($pr_dir . '/schema') && file_exists($pr_dir . '/schema/global.json');
    $managed_count = count(get_posts([
        'numberposts' => -1, 'post_status' => 'any',
        'meta_key' => '_practicerank_managed', 'meta_value' => '1',
    ]));

    ?>
    <div class="wrap">
        <h1>PracticeRank SEO</h1>

        <div style="background:#fff;border:1px solid #ccd0d4;border-radius:4px;padding:16px;margin:16px 0;">
            <h2 style="margin-top:0;">Connection Status</h2>
            <table class="widefat" style="max-width:500px;">
                <tr><td>llms.txt</td><td><?php echo $has_llms ? '<span style="color:green;">&#10004; Active</span>' : '<span style="color:#999;">Not yet generated</span>'; ?></td></tr>
                <tr><td>Schema Markup</td><td><?php echo $has_schema ? '<span style="color:green;">&#10004; Active</span>' : '<span style="color:#999;">Not yet pushed</span>'; ?></td></tr>
                <tr><td>Managed Content</td><td><?php echo $managed_count; ?> posts/pages</td></tr>
                <tr><td>REST API</td><td><code><?php echo get_rest_url(null, 'practicerank/v1/health'); ?></code></td></tr>
            </table>
        </div>

        <form method="post" action="options.php">
            <?php settings_fields('practicerank_settings'); ?>

            <table class="form-table">
                <tr>
                    <th scope="row">API Key</th>
                    <td>
                        <input type="text" name="<?php echo PRACTICERANK_OPTION_PREFIX; ?>api_key"
                               value="<?php echo esc_attr($api_key); ?>"
                               class="regular-text" readonly style="font-family:monospace;" />
                        <p class="description">Share this key with your PracticeRank account manager. Used to authenticate API requests.</p>
                    </td>
                </tr>
                <tr>
                    <th scope="row">Schema Injection</th>
                    <td>
                        <label>
                            <input type="checkbox" name="<?php echo PRACTICERANK_OPTION_PREFIX; ?>schema_enabled" value="1"
                                   <?php checked($schema_enabled, '1'); ?> />
                            Inject JSON-LD schema markup into page &lt;head&gt;
                        </label>
                    </td>
                </tr>
                <tr>
                    <th scope="row">AI Robots.txt</th>
                    <td>
                        <label>
                            <input type="checkbox" name="<?php echo PRACTICERANK_OPTION_PREFIX; ?>robots_enabled" value="1"
                                   <?php checked($robots_enabled, '1'); ?> />
                            Add AI crawler rules to robots.txt
                        </label>
                    </td>
                </tr>
                <tr>
                    <th scope="row">Content as Draft</th>
                    <td>
                        <label>
                            <input type="checkbox" name="<?php echo PRACTICERANK_OPTION_PREFIX; ?>content_as_draft" value="1"
                                   <?php checked($content_as_draft, '1'); ?> />
                            Push new content as drafts (requires manual publish)
                        </label>
                        <p class="description">When unchecked, content pushed via API will be published immediately.</p>
                    </td>
                </tr>
            </table>

            <?php submit_button(); ?>
        </form>
    </div>
    <?php
}

// ─── Meta Description Output (for themes without SEO plugin) ────────────────

add_action('wp_head', function() {
    if (defined('WPSEO_VERSION') || defined('RANK_MATH_VERSION') || defined('AIOSEO_VERSION')) return;

    if (is_singular()) {
        $desc = get_post_meta(get_the_ID(), '_practicerank_meta_description', true);
        if ($desc) {
            echo '<meta name="description" content="' . esc_attr($desc) . '" />' . "\n";
        }
    }
}, 5);
