# IPHS 400 Mini-Project #2: Kenyon Baseball Alumni CMS

Samuel Hodges · 2026-10-06 · Repo: https://github.com/samuelphodges/iphs400-mp2-cms · Live site: https://samuelphodges.github.io/iphs400-mp2-cms/

## 1. What did you build, and which grill decisions were yours?

For the project, I built a CMS and a static public website for my client, The Kenyon Varsity Baseball Alumni. This included pages for team schedule, Alumni events, and an Alumni network contact list. Grill decisions that I made included page names for the site, alumni network showing names only, and the editor (Joe) being able to post on two of the pages without Matt's approval. I made the change for the page names by overriding the model's suggestions as they didn't fit what I was looking for. For the contact list showing names only, this came partly from a suggestion from the model due to privacy concerns. However, I chose specifically what I wanted to appear while taking into account these concerns. The capabilities of the editor came up in the grill, as well, and I decided specifically that Joe could make edits to two of the pages without Matt's approval. 

## 2. Where did the AI drift or invent something, and what caught it?

The AI wrote a test that looked more thorough than it was. In T01 the model added test_every_admin_route_redirects_anonymous_visitors, with a comment saying it checks every admin route so that "a new route cannot escape". But it listed routes from app.routes, and in this version of FastAPI, routes added through include_router don't show up there. The test only ever checked two routes, /admin and /admin/refused, and never looked at the pages, posts, listings or users routes added in later tickets. I didn't catch this problem as each test after a ticket passed. The mistake was not caught until T08 when a test of /admin failed. The model added a stricter test to fix this issue. 

## 3. Which skills, prompts, and resources did you use, and why those?

I used the mattpocock skills throughout this project and I found them very useful. The specific ones that were most useful were /grill-with-docs, /implement, and /code-review. These allowed me to ensure the model and I were on the same page, each ticket was implemented separately, and checks on each ticket. By breaking up the project in to multiple tasks and tickets, then running the implement skill, I was better able to check the model's productivity and progress by catching any potential errors early on. Had I tried to this all at once, I feel it was much more likely to lead to mistakes that would take longer to clean up. 

## 4. What would you add next, and what did the budget data tell you?

From the budget data, I learned that I used a lot less context and tokens that I originally planned for. This is because the majority of the tickets were a lot smaller than anticipated, with only T08 being a relatively large ticket. In my plan, the expected size was 15% per ticket while the average was roughly 4% per. 

If I were to build something next for this website, it would probably include making it a website for actual use of the Alumni. Given this was just a project, the website only includes example names and not a full list of opted-in Alumni. Also, I would clean up the website visuals to make it fit a Kenyon theme. 
