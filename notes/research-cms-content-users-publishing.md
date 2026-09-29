# How CMSs model content, users/roles, and publishing: WordPress, Drupal, and static-site generators

Scope: primary sources only (official docs, source code). Every claim carries the URL that owns it.
Anything I could not confirm against a primary source is marked **UNVERIFIED**. Fetched 2026-09-28.
Note: several drupal.org pages now 302-redirect to new.drupal.org; the URLs cited are the ones I fetched
successfully. Doc pages were read through a summarising fetch tool, so quotes are as returned by it; the
WordPress schema and Drupal API claims are from source/API pages.

## 1. Content model

### WordPress: one table, typed by `post_type`, extended by meta and taxonomies

- Everything is a "post" row. Built-in post types are "post, page, attachment, revision, and menu";
  developers add more with `register_post_type()`.
  https://developer.wordpress.org/plugins/post-types/registering-custom-post-types/
- The type is a column: `post_type varchar(20) NOT NULL default 'post'` in the `posts` table definition
  (source). Docs confirm the 20-char limit because "the `post_type` column in the database is currently a
  VARCHAR field of that length".
  https://raw.githubusercontent.com/WordPress/wordpress-develop/trunk/src/wp-admin/includes/schema.php
  https://developer.wordpress.org/plugins/post-types/registering-custom-post-types/
- Extra fields are post meta: key/value pairs, where `meta_key` is a reference identifier and `meta_value` "can be a
  string, integer, or array" (arrays are serialized). Keys starting with `_` are hidden from the custom-fields list
  on the edit screen. https://developer.wordpress.org/plugins/metadata/managing-post-metadata/
  Storage is a `postmeta` table with `post_id`, `meta_key varchar(255)`, `meta_value longtext` (source above).
- Classification is by taxonomies: "Taxonomies are the method of classifying content and data in WordPress."
  Categories are hierarchical, tags non-hierarchical, custom taxonomies are allowed, and "terms" are the items in
  a taxonomy. https://developer.wordpress.org/themes/basics/categories-tags-custom-taxonomies/
  Tables: `terms`, `term_taxonomy` (with a `taxonomy varchar(32)` column) and `term_relationships`
  (`object_id`, `term_taxonomy_id`) (schema source above).

### Drupal: typed entities, bundles, and configurable fields

- A content entity is "an item of content data, which can consist of text, HTML markup, images, attached files,
  and other data"; entity types are divided into subtypes; a content type is an entity subtype of the Node
  module's content item entity type; data lives in individual fields, each "one type of data".
  https://www.drupal.org/docs/user_guide/en/planning-data-types.html
- "Bundles are variants of an entity type. For example, with the node entity type, the bundles are the different
  node types, such as 'article' and 'page'." A bundle is typically a configuration entity.
  Content entities "consist of configurable and base fields and can have revisions and support translations";
  configuration entities are stored in the `config` table.
  https://www.drupal.org/docs/drupal-apis/entity-api/introduction-to-entity-api-in-drupal-8
- Contrast with WordPress: the schema is configured per type (fields are added to a content type so all items
  of that type share the same field set), where WordPress uses one shared table plus free-form meta.
  (Field-sharing per type: user guide URL above. The contrast is my synthesis.)
- Drupal taxonomy as a content concept: **UNVERIFIED** (I did not fetch a Drupal taxonomy primary source).

### Static-site generators: files plus front matter, collections, data files

- Hugo: front matter can be JSON, TOML, or YAML (auto-detected).
  https://gohugo.io/content-management/front-matter/
  The source layout mirrors the output: "Hugo assumes that the same structure that works to organize your source
  content is used to organize the rendered site"; top-level directories in `content/` are sections; page bundles
  package resources with a page. https://gohugo.io/content-management/organization/
  Taxonomy = "a categorization that can be used to classify content", term = "a key within the taxonomy",
  assigned by plural name in front matter (`tags:`, `categories:`).
  https://gohugo.io/content-management/taxonomies/
  Data files: a `data` directory at project root; CSV, JSON, TOML, YAML, XML. https://gohugo.io/content-management/data-sources/
- Jekyll: posts live in `_posts` as `YEAR-MONTH-DAY-title.MARKUP` and "must begin with front matter"
  https://jekyllrb.com/docs/posts/ ; a file with a YAML front matter block "will be processed by Jekyll as a
  special file", files without it are not processed https://jekyllrb.com/docs/front-matter/ .
  Collections group related content, are declared in `_config.yml`, live in an `_`-prefixed folder, and get pages
  only with `output: true` https://jekyllrb.com/docs/collections/ .
  Tags come from front matter; categories can also come from directory path above `_posts`
  https://jekyllrb.com/docs/posts/ . Data: `_data` folder with YAML, JSON, TSV or CSV
  https://jekyllrb.com/docs/datafiles/
- Eleventy: collections are built from a `tags` value in front matter (or the Collections API); "`tags` have a
  singular purpose in Eleventy: to construct collections of content" https://www.11ty.dev/docs/collections/ .
  Front matter defaults to YAML, also JSON and (v3+) JavaScript https://www.11ty.dev/docs/data-frontmatter/ .
  Global data is a `_data` directory; that page describes JSON and JavaScript files and links to a
  "Custom Data File Formats" page for others https://www.11ty.dev/docs/data-global/ (other formats: not verified here).

## 2. Users and roles

### WordPress: users hold roles; roles are sets of capabilities

- "A role defines a set of capabilities for a user"; "Capabilities define what a role can and can not do: edit
  posts, publish posts, etc." Six default roles: Super Admin, Administrator, Editor, Author, Contributor,
  Subscriber. `add_role()` creates roles, and sequential calls with the same role do nothing (roles persist in the
  DB). `current_user_can()` checks a capability or role.
  https://developer.wordpress.org/plugins/users/roles-and-capabilities/
- Storage: the role list (name, display name, capability array) is kept under an option key `<prefix>user_roles`
  https://raw.githubusercontent.com/WordPress/wordpress-develop/trunk/src/wp-includes/class-wp-roles.php ;
  users are in a `users` table (`user_login`, `user_pass varchar(255)`) with a `usermeta` key/value table (schema source above).
- Publishing-relevant capability split (from the role/capability lists): Editor and Author include `publish_posts`;
  Contributor has `edit_posts`, `delete_posts`, `read` but no `publish_posts`; Subscriber has only `read`.
  https://wordpress.org/documentation/article/roles-and-capabilities/
  Effect in UI: users with `edit_posts` but not `publish_posts` see "Submit for Review" instead of "Publish".
  https://wordpress.org/documentation/article/post-status/

### Drupal: users hold roles; roles are sets of permissions

- "Anyone who visits your website is a user": anonymous, authenticated, and User 1. Permissions govern actions;
  "permissions are grouped into roles". Built-in roles: anonymous, authenticated, administrator.
  https://www.drupal.org/docs/user_guide/en/user-concept.html
- A role is a configuration entity (`Role` extends `ConfigEntityBase`, id `user_role`) holding a permissions array;
  an admin role gets `hasPermission()` true for everything.
  https://api.drupal.org/api/drupal/core%21modules%21user%21src%21Entity%21Role.php/class/Role/11.x
- Difference from WordPress (my synthesis from the two sources above): Drupal permissions are provided by modules and
  attached to roles in config; WordPress capabilities are stored as role data and checked in code by name.

### Static-site generators: no user or role model in the tool

- None of the Hugo, Jekyll, or Eleventy pages I fetched define users or roles. Who can publish is determined by who
  can push to the repository/host: Hugo's GitHub Pages guide says "whenever you push a change from your local Git
  repository, GitHub Pages will rebuild and deploy your site" https://gohugo.io/host-and-deploy/host-on-github-pages/ ;
  Jekyll: "Your site is automatically generated by GitHub Pages when you push your source files"
  https://jekyllrb.com/docs/github-pages/ .
- "SSGs have no built-in access control" is an absence claim. I found no page that states it. **UNVERIFIED** as an
  explicit statement; it is inferred from the docs having no such section.

## 3. Publishing

### WordPress: a `post_status` column

- "The status is stored in the post_status field in the wp_posts table." Eight built-in statuses: `publish`
  (viewable by everyone), `future` (scheduled), `draft`, `pending` (awaiting a user with `publish_posts`), `private`,
  `trash`, `auto-draft`, `inherit` (child posts take the parent's status). "Save Draft" sets `draft`, "Publish" sets
  `publish`; users without `publish_posts` submit to `pending`. Custom statuses via `register_post_status()`.
  https://wordpress.org/documentation/article/post-status/
- `register_post_status()`'s `public` arg: "Whether posts of this status should be shown in the front end of the site.
  Default false." https://developer.wordpress.org/reference/functions/register_post_status/
- `wp_insert_post()` defaults `post_status` to `'draft'` and `post_type` to `'post'`; for `'future'` you must give
  `post_date`; a `future` post whose date has passed becomes `publish`.
  https://developer.wordpress.org/reference/functions/wp_insert_post/
  (The schema column default is `'publish'`; see the schema source above. The two defaults are at different layers.)
- Publishing is a live state change: the site is rendered on request from the DB (the request-time rendering claim is
  **UNVERIFIED**, not fetched).

### Drupal: a published flag, optionally driven by Workflows + Content Moderation

- Core: `EntityPublishedInterface` provides `isPublished()`, `setPublished()`, `setUnpublished()`
  https://api.drupal.org/api/drupal/core%21lib%21Drupal%21Core%21Entity%21EntityPublishedInterface.php/interface/EntityPublishedInterface/11.x ;
  `EntityPublishedTrait` defines a boolean "Published" base field, revisionable and translatable, default TRUE
  https://api.drupal.org/api/drupal/core%21lib%21Drupal%21Core%21Entity%21EntityPublishedTrait.php/trait/EntityPublishedTrait/11.x
  Content type setting: the "Published" option under Publishing options sets the default for new items; it does not
  change existing items. https://www.drupal.org/docs/user_guide/en/structure-content-type.html
- Workflows module: "manage workflow with states and transitions"; states are "the different statuses your content can
  have (draft, published etc)". https://www.drupal.org/docs/8/core/modules/workflows/overview
- Content Moderation: each state carries `published` and `default_revision` flags. Editorial example: Published =
  `published: true, default_revision: true`; Draft = `published: false, default_revision: false`; Archived also exists.
  Transitions (e.g. Publish, Archive) move content between states. Authors can create/edit but not publish; an editor role
  transitions to Published. "To unpublish a node you must set the state to Archived on the published revision."
  https://www.drupal.org/docs/8/core/modules/content-moderation/overview
- Consequence: a draft edit of already-published content can exist as a non-default revision while the last published
  revision stays live (default revision flag, same source).
- Who can see unpublished content (permissions like "View own unpublished content", "View the latest version") is
  mentioned in the same moderation guide; a full list of node-view permissions is **UNVERIFIED**.

### Static-site generators: a build step filters files

- Hugo: "By default, Hugo does not publish draft pages when you build your project"; use `--buildDrafts`.
  https://gohugo.io/methods/page/draft/ . `publishDate` controls visibility (pages before it are not rendered unless
  `--buildFuture`); `expiryDate` likewise with `--buildExpired`.
  https://gohugo.io/content-management/front-matter/ ; flags: -D/--buildDrafts, -F/--buildFuture, -E/--buildExpired
  https://gohugo.io/commands/hugo/
- Jekyll: drafts are "posts without a date in the filename", kept in `_drafts`, rendered only with `--drafts`
  https://jekyllrb.com/docs/posts/ . `published: false` in front matter excludes a post
  https://jekyllrb.com/docs/front-matter/ . Flags `--drafts`, `--future`, `--unpublished`, and defaults `future: false`,
  `unpublished: false` https://jekyllrb.com/docs/configuration/options/ , https://jekyllrb.com/docs/configuration/default/
- Eleventy: no built-in draft flag on the pages I read; the documented pattern is a preprocessor: "Set `draft: true`
  anywhere in a file's data cascade and that file will be only be built when using Eleventy in `--serve` or `--watch`
  modes", and the docs say a publish-date feature could be added the same way.
  https://www.11ty.dev/docs/config-preprocessors/
- Publishing = run the build and deploy the output (see the Hugo/Jekyll deploy pages in section 2).

## 4. Comparison

| Aspect | WordPress | Drupal | Hugo / Jekyll / Eleventy |
|---|---|---|---|
| Unit of content | Row in posts table, typed by `post_type` | Content entity of an entity type; node bundle = content type | A file (Markdown + front matter) |
| Custom fields | `postmeta` key/value | Configurable fields per bundle | Front matter keys |
| Classification | Taxonomies/terms tables | Taxonomy: UNVERIFIED | Hugo taxonomies; Jekyll tags/categories; 11ty `tags` = collections |
| Shared data | Options/meta | Config entities | `data/` or `_data/` files |
| Users | `users` + `usermeta` tables | User entities | None in tool (UNVERIFIED as explicit statement) |
| Access model | Role -> capabilities | Role (config) -> permissions | Repo/host permissions (inferred) |
| Draft state | `post_status = draft` | Unpublished / Draft moderation state | Hugo `draft`, Jekyll `_drafts`/`published:false`, 11ty preprocessor |
| Review step | `pending` (needs `publish_posts`) | Workflow states + transitions | None in tool |
| Scheduling | `future` status | Not covered in fetched sources | Hugo `publishDate`; Jekyll future-date; 11ty custom |
| Publish action | Status change, live | Published flag / state transition | Build + deploy |

## 5. Implications for our design (FastAPI + Jinja + SQLite, `cms publish` -> `site/`)

These are my inferences from the sources above, not claims made by them.

1. Our design is a hybrid: WordPress/Drupal-style DB content and users for editing, SSG-style build for output. The status
   filter that WordPress applies at request time (`post_status`) and Hugo/Jekyll apply at build time (draft flags) becomes a
   query at `cms publish` time (`WHERE status = 'published'`). That is how "drafts never leave the DB" is enforced structurally.
2. Start with a small status set: WordPress's `draft` / `pending` / `publish` (plus `future` if scheduling is wanted) covers
   the review flow with a single column. Drupal's Content Moderation shows the cost of going further (states, transitions,
   default revision), which is likely out of scope for a mini-project.
3. Keep an explicit "who may publish" check. WordPress ties `pending` vs `publish` to the `publish_posts` capability; Drupal
   ties transitions to role permissions. A minimal equivalent is roles as named permission sets, checked in code
   (for example writer: create/edit/submit; editor: publish).
4. Model content as one `content` table with a type column and a small typed-fields JSON or table before adding
   WordPress-style free-form meta. Drupal's per-bundle fields give validation; WordPress meta gives flexibility.
5. Copy the SSG rules for scheduling and expiry only if needed: Hugo's `publishDate`/`expiryDate` are evaluated at build time,
   so a scheduled post only appears at the next `cms publish` run (nothing runs automatically). Jekyll's default `future: false`
   is the same idea.
6. Unlike Drupal (default revision vs latest revision), a published post edited later would in a naive design change the
   live row. Decide whether an edited published item stays live until re-published (Drupal-like) or needs two copies. Because
   `site/` is only regenerated by `cms publish`, the "last published output stays live until the next publish" behaviour
   comes for free.
