# Token budget plan

## Model choice

The Model I am using is Sonnet 5.5 at medium effort. The reason I chose this is for a couple reasons. First off, Sonnet 5.5 has a good balance between mid level-intelligence and middle of the pack cost (tokens). This is ideal for my project which doesn't require super high level thinking but does conserving token usage. As for medium effort, this is the default level and is all that I require in order to complete the required tasks and skills. 

## Plan

| Stage | Model | Effort | % of a 5 hour window |
|---|---|---|---|
| `/research`, quick lookups | Sonnet | medium |2% |
| `/grill-with-docs`, `/to-spec`, `/to-tickets` | Sonnet | medium | 20% |
| `/implement` + `/tdd` (per ticket) | Sonnet | medium |10% |
| `/code-review` (per ticket) | Sonnet | medium |5% |

## Questions

**1. How many 5-hour windows will the 9 tickets take?**

It will take roughly 2 5-hour windows given my estimates above. 

**2. How much of one week is that?**

Roughly 70% of my weekly cap

**3. Which stage will you cut first if you are wrong?**

Because my model is already a releatively cheap one with low effort, I don't have much wiggle room in terms of switching effort and model. Likely the stage I would cut would be /code-review