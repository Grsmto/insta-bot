# Insta-bot

A single-Account Instagram commenter: persist one Session identity, check a Watch list on a schedule, and post an AI-written Comment on newly seen posts.

## Language

**Account**:
An Instagram identity the commenter can log in as and comment from. Identified by its Instagram username. The commenter can be pointed at a different Account by changing credentials. Mapping uses a test Account.
_Avoid_: bot account, user, client

**Watch list**:
The set of public Instagram profiles whose posts are checked for new activity. Exactly one Watch list per Account. Stored in a database; there is no UI in this spec.
_Avoid_: targets, popular accounts, following list

**Watched profile**:
A public Instagram profile that is a member of the Watch list. Identified by Instagram user pk; username is what was typed when it was added.
_Avoid_: target, follow, content creator

**Session identity**:
The stable device and session Instagram sees when the Account posts a Comment, persisted across runs so the Account looks like the same person each time.
_Avoid_: profile, fingerprint (on its own), browser profile

**Post**:
An Instagram media item on a watched profile, including caption, media, and comments from other people.
_Avoid_: media, reel, content

**Comment**:
Text generated in the Account's Persona from a Post's caption, image, and recent comments, then posted from the Account.
_Avoid_: reply, message

**Persona**:
The per-Account writing instructions used to generate a Comment: who the Account is, which languages it uses, and how it sounds.
_Avoid_: prompt, personality, brand voice, bot character

**New post**:
A Post on a watched profile published within a configurable age cutoff (default 24 hours) that this Account has no Comment record for.
_Avoid_: latest post, unseen media, backfill

**Comment record**:
The stored fact that the Account already commented on a Post, including the Comment text, the Post URL, and the Post and Comment pks. There is no Comment URL.
_Avoid_: log, history

**Run**:
One check-and-comment cycle for an Account: read the Watch list, post Comments on New posts up to the cap, persist Comment records, then exit.
_Avoid_: job, tick, cron, hourly job
