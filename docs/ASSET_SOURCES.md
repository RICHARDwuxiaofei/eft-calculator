# Visual asset sources

## Application icon

`src/tarkov_armor_sim/resources/icons/app-icon.png` and `.ico` are original project
assets generated for EFT Calculator on 2026-07-30. The design is an abstract armor
plate, projectile, and impact arc. It does not use the Escape from Tarkov logo,
characters, screenshots, or existing game artwork.

Generation prompt summary:

> Original vector-like desktop icon: a charcoal ballistic plate intersected by a
> brass projectile and analytical impact arc; no text, game logo, characters,
> watermark, or copyrighted game imagery.

## Item images

The small ammunition, armor plate, soft armor, and helmet images under
`resources/items/` were retrieved from the Escape from Tarkov Wiki through its
MediaWiki API. Exact file titles, description pages, original URLs, sizes, and
retrieval time are recorded in `resources/items/sources.json`.

These item images are reference assets associated with Escape from Tarkov. They
are **not licensed under this project's MIT License**. Rights remain with
Battlestate Games and/or the respective file owners. Their inclusion does not
imply endorsement or affiliation. Downstream redistributors are responsible for
reviewing the source file pages and applicable terms.

Data/API and category references:

- https://escapefromtarkov.fandom.com/wiki/Category:Ammunition_icons
- https://escapefromtarkov.fandom.com/api.php
- https://github.com/the-hideout/tarkov-api/blob/main/docs/graphql-examples.md

