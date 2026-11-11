# Native Mem0's order in the smoke (s14b)

Replayed 90 probes; the replay reproduced 90 of 90 recorded fetches (the row count, and the rows shown, their order and scores; a row the sharing rule hid is recorded only as a count). In 90 of 90, every row's Mem0 score is its squared L2 distance to the question, capped at 1.0. Mem0's history: {'ADD': 1020, 'DELETE': 30}.

| Probe | n | target nearest by cosine | target in the fetch | target's Mem0 rank, median (range) | rows at 1.0 above it, median (range) | target's cosine, range |
|---|---:|---:|---:|---|---|---|
| recall | 30 | 26 | 4 | 24.5 (1 to 29) | 21 (0 to 28) | 0.47 to 0.87 |
| recency | 30 | 15 | 1 | 26 (1 to 32) | 23 (0 to 30) | 0.50 to 0.85 |
| contradiction | 30 | 15 | 2 | 27.5 (2 to 34) | 23 (1 to 32) | 0.48 to 0.80 |

**User 0, recall** (`u000-p3-recall`): "Who do I report to?", expected
Greta Sandvik; passed, through an earlier probe's answer. 27 rows in the
store.

Target row: rank 27 of 27, Mem0 score 0.889, cosine 0.556 (rank 1 by
cosine): "Jordan McAllister reports to Greta Sandvik."

| Rank | Score | Cosine | Seen | Row |
|---:|---:|---:|---|---|
| 1 | 1.000 | 0.492 | in block | User sends issues related to their Weather Data API project to Rollbar for tracking and management. |
| 2 | 1.000 | 0.483 | in block | User is a member of the Ariamont choir and sings with them. |
| 3 | 1.000 | 0.476 | in block | User goes to a running club that gathers in Wychwood Park. |
| 4 | 1.000 | 0.465 | hidden | Ravelstone Security is attempting to recruit User's team lead, as mentioned off the record. |
| 5 | 1.000 | 0.464 | in block | User's team lead is Greta Sandvik, who supervises Jordan McAllister on the Weather Data API project. |
| 6 | 1.000 | 0.455 | in block | Jordan McAllister prefers formal responses in communication. |
| 7 | 1.000 | 0.450 | in block | User meets with Lena Fischbach one-on-one every week. |
| 8 | 1.000 | 0.450 | in block | User's name is Jordan McAllister. |
| 9 | 1.000 | 0.447 | in block | User was recommended Slack or Microsoft Teams for real-time communication and collaboration among team members, especially for complex projects like the Weather Data API. |
| 10 | 1.000 | 0.446 | in block | User's team is having a game night at Meeplehaus. |
| 11 | 1.000 | 0.444 | cut | User has a weekly one-on-one meeting with Sofia Lindqvist. |
| 12 | 1.000 | 0.444 | cut | User's team uses Rollbar for tracking and managing issues related to their Weather Data API project. |
| 13 | 1.000 | 0.436 | cut | User's next steps for their Weather Data API project are to investigate and fix preprocessing bugs, run the experiment on different weather datasets, collaborate with QA to validate data ingestion flows, and document findings from preprocessing tests. |
| 14 | 1.000 | 0.426 | cut | Jordan McAllister uses tools like Visual Studio Code, Docker, Git, and Postman for development and is focused on the Weather Data API project. His next steps include investigating preprocessing bugs, running experiments on weather datasets, collaborating with QA to validate data ingestion flows, and documenting findings from preprocessing tests. |
| 15 | 1.000 | 0.423 | cut | User's staging server for their Weather Data API project was relocated to bittern-06 as of November 9, 2026. |
| 16 | 1.000 | 0.416 | cut | User registered for the Brightnoon lunch talk series. |
| 17 | 1.000 | 0.413 | cut | User arranged the sprint retrospective to be held via a Mattermost call. |
| 18 | 1.000 | 0.409 | cut | User is enrolled in a nighttime class for calligraphy. |
| 19 | 1.000 | 0.406 | cut | User is working on a Weather Data API and is currently testing data preprocessing accuracy on hourly data ingestion. Their goals include ensuring the API handles large volumes of weather data efficiently, improving data preprocessing for better model predictions, and incorporating error handling for missing or corrupt data. |
| 20 | 1.000 | 0.404 | cut | User uses the tern-02 staging server for deployment in their Weather Data API project. |
| 21 | 1.000 | 0.398 | cut | User attends their book club gatherings at Hearth & Page. |
| 22 | 1.000 | 0.396 | cut | Jordan McAllister prefers to use Visual Studio Code, Docker, Git, and Postman for development. |
| 23 | 1.000 | 0.378 | cut | Jordan McAllister goes swimming at the Seabright club. |
| 24 | 1.000 | 0.377 | cut | Jordan McAllister's preferred programming language is Python. |
| 25 | 1.000 | 0.342 | cut | Jordan McAllister uses the Everforest color theme in their editor. |
| 26 | 1.000 | 0.328 | cut | User's current blockers in their Weather Data API project include an unexpected drop in predicted accuracy due to preprocessing bugs. |

**User 0, recency** (`u000-p4-recency`): "Which staging server do we
deploy to?", expected bittern-06, stale tern-02; failed. 28 rows in the
store.

Target row: rank 27 of 28, Mem0 score 0.724, cosine 0.638 (rank 2 by
cosine): "User's staging server for their Weather Data API project was
relocated to bittern-06 as of November 9, 2026."

| Rank | Score | Cosine | Seen | Row |
|---:|---:|---:|---|---|
| 1 | 1.000 | 0.475 | in block | Jordan McAllister prefers to use Visual Studio Code, Docker, Git, and Postman for development. |
| 2 | 1.000 | 0.461 | in block | User was recommended Slack or Microsoft Teams for real-time communication and collaboration among team members, especially for complex projects like the Weather Data API. |
| 3 | 1.000 | 0.461 | in block | User reports to Greta Sandvik, who is their team lead and supervises the Weather Data API project. |
| 4 | 1.000 | 0.460 | in block | User's team lead is Greta Sandvik, who supervises Jordan McAllister on the Weather Data API project. |
| 5 | 1.000 | 0.451 | hidden | Ravelstone Security is attempting to recruit User's team lead, as mentioned off the record. |
| 6 | 1.000 | 0.451 | in block | Jordan McAllister uses tools like Visual Studio Code, Docker, Git, and Postman for development and is focused on the Weather Data API project. His next steps include investigating preprocessing bugs, running experiments on weather datasets, collaborating with QA to validate data ingestion flows, and documenting findings from preprocessing tests. |
| 7 | 1.000 | 0.451 | in block | User's next steps for their Weather Data API project are to investigate and fix preprocessing bugs, run the experiment on different weather datasets, collaborate with QA to validate data ingestion flows, and document findings from preprocessing tests. |
| 8 | 1.000 | 0.444 | in block | User is working on a Weather Data API and is currently testing data preprocessing accuracy on hourly data ingestion. Their goals include ensuring the API handles large volumes of weather data efficiently, improving data preprocessing for better model predictions, and incorporating error handling for missing or corrupt data. |
| 9 | 1.000 | 0.439 | in block | User's team uses Rollbar for tracking and managing issues related to their Weather Data API project. |
| 10 | 1.000 | 0.437 | in block | User is a member of the Ariamont choir and sings with them. |
| 11 | 1.000 | 0.437 | cut | User sends issues related to their Weather Data API project to Rollbar for tracking and management. |
| 12 | 1.000 | 0.401 | cut | User's current blockers in their Weather Data API project include an unexpected drop in predicted accuracy due to preprocessing bugs. |
| 13 | 1.000 | 0.388 | cut | User's name is Jordan McAllister. |
| 14 | 1.000 | 0.383 | cut | Jordan McAllister reports to Greta Sandvik. |
| 15 | 1.000 | 0.372 | cut | Jordan McAllister uses the Everforest color theme in their editor. |
| 16 | 1.000 | 0.372 | cut | User goes to a running club that gathers in Wychwood Park. |
| 17 | 1.000 | 0.367 | cut | User has a weekly one-on-one meeting with Sofia Lindqvist. |
| 18 | 1.000 | 0.363 | cut | Jordan McAllister's preferred programming language is Python. |
| 19 | 1.000 | 0.362 | cut | User registered for the Brightnoon lunch talk series. |
| 20 | 1.000 | 0.362 | cut | User arranged the sprint retrospective to be held via a Mattermost call. |
| 21 | 1.000 | 0.352 | cut | Jordan McAllister prefers formal responses in communication. |
| 22 | 1.000 | 0.340 | cut | User attends their book club gatherings at Hearth & Page. |
| 23 | 1.000 | 0.338 | cut | User is enrolled in a nighttime class for calligraphy. |
| 24 | 1.000 | 0.319 | cut | User meets with Lena Fischbach one-on-one every week. |
| 25 | 1.000 | 0.307 | cut | Jordan McAllister goes swimming at the Seabright club. |
| 26 | 0.998 | 0.501 | cut | User's team is having a game night at Meeplehaus. |

**User 1, recall** (`u001-p3-recall`): "Who am I pairing with on my
project?", expected Jonas Albrecht; failed. 25 rows in the store.

Target row: rank 25 of 25, Mem0 score 0.754, cosine 0.623 (rank 1 by
cosine): "User is pairing with Jonas Albrecht for their Dynamic Website
Optimization project."

| Rank | Score | Cosine | Seen | Row |
|---:|---:|---:|---|---|
| 1 | 1.000 | 0.499 | in block | Alex Carter prefers to use Visual Studio Code, Docker, Git, and Postman for development. |
| 2 | 1.000 | 0.492 | in block | User's team stores their design documents in Slite. |
| 3 | 1.000 | 0.491 | in block | User is working on Dynamic Website Optimization and is currently experimenting with caching mechanisms using Flask and Redis. Their goals include improving website load times, ensuring caching implementation reduces server load, evaluating the scalability of the caching solution, and documenting all results for future reference. |
| 4 | 1.000 | 0.484 | in block | User's name is Alex Carter. |
| 5 | 1.000 | 0.472 | hidden | User needs to see Dr. Okafor for a confidential follow-up appointment. |
| 6 | 1.000 | 0.462 | in block | Alex Carter's preferred programming language is Python. |
| 7 | 1.000 | 0.449 | in block | Alex Carter spends weekends playing Everdell with their friends. |
| 8 | 1.000 | 0.446 | in block | User's team offsite has been relocated to Kaunas. |
| 9 | 1.000 | 0.444 | in block | User's Dynamic Website Optimization project stores service information in TimescaleDB. |
| 10 | 1.000 | 0.437 | in block | Alex Carter reports to Lena Fischbach. |
| 11 | 1.000 | 0.426 | cut | Alex Carter uses the Solarized color theme in their editor. |
| 12 | 1.000 | 0.423 | cut | User goes to Fernbrook Park for their running club meetings. |
| 13 | 1.000 | 0.415 | cut | User volunteers at the Oakwell food bank. |
| 14 | 1.000 | 0.391 | cut | Alex Carter gets their coffee beans from Cinderbean. |
| 15 | 1.000 | 0.390 | cut | Alex Carter's terminal font is set to Monospace. |
| 16 | 1.000 | 0.383 | cut | Alex Carter goes swimming at the Marlowe club. |
| 17 | 1.000 | 0.363 | cut | Alex Carter prefers formal responses in communication. |
| 18 | 0.990 | 0.505 | cut | User's next steps for Dynamic Website Optimization include debugging integration issues with Redis, assessing load time improvements using test cases, scaling the implementation for different user loads, and preparing documentation to share findings with their team. |
| 19 | 0.987 | 0.506 | cut | User was recommended potential codenames for the Dynamic Website Optimization project, including 'SpeedBoost,' 'CacheMaster,' and 'LoadLight,' reflecting optimization and caching themes. |
| 20 | 0.978 | 0.511 | cut | User's manager is named Elif Kaya. |
| 21 | 0.954 | 0.523 | cut | User's team is having its offsite in Utrecht. |
| 22 | 0.946 | 0.527 | cut | User is facing a blocker in integrating Redis with their existing Flask application while working on Dynamic Website Optimization. |
| 23 | 0.885 | 0.558 | cut | User is working on the Dynamic Website Optimization project with Jonas Albrecht and is currently focused on debugging integration issues with Redis, assessing load time improvements, scaling the implementation, and preparing documentation. |
| 24 | 0.868 | 0.566 | cut | User was suggested to discuss assigning an internal codename for the Dynamic Website Optimization project with Jonas Albrecht or Elif Kaya to streamline communication. |

**User 1, recency** (`u001-p4-recency`): "Where is the team offsite?",
expected Kaunas, stale Utrecht; failed. 28 rows in the store.

Target row: rank 28 of 28, Mem0 score 0.503, cosine 0.749 (rank 1 by
cosine): "User's team offsite has been relocated to Kaunas."

| Rank | Score | Cosine | Seen | Row |
|---:|---:|---:|---|---|
| 1 | 1.000 | 0.499 | in block | User goes to Fernbrook Park for their running club meetings. |
| 2 | 1.000 | 0.483 | in block | User was recommended to reach out to Lena Fischbach, who reports to them, for details about team composition or pairing arrangements for the Dynamic Website Optimization project. |
| 3 | 1.000 | 0.471 | in block | User's team stores their design documents in Slite. |
| 4 | 1.000 | 0.448 | in block | Alex Carter spends weekends playing Everdell with their friends. |
| 5 | 1.000 | 0.413 | in block | User is pairing with Jonas Albrecht for their Dynamic Website Optimization project. |
| 6 | 1.000 | 0.412 | in block | User's manager is named Elif Kaya. |
| 7 | 1.000 | 0.408 | in block | User volunteers at the Oakwell food bank. |
| 8 | 1.000 | 0.404 | in block | User is working on the Dynamic Website Optimization project and uses tools like Visual Studio Code, Docker, Git, and Postman, with design documents stored in Slite. |
| 9 | 1.000 | 0.398 | in block | User's Dynamic Website Optimization project stores service information in TimescaleDB. |
| 10 | 1.000 | 0.397 | in block | User's name is Alex Carter. |
| 11 | 1.000 | 0.395 | cut | Alex Carter goes swimming at the Marlowe club. |
| 12 | 1.000 | 0.392 | cut | User is working on the Dynamic Website Optimization project with Jonas Albrecht and is currently focused on debugging integration issues with Redis, assessing load time improvements, scaling the implementation, and preparing documentation. |
| 13 | 1.000 | 0.391 | cut | Alex Carter reports to Lena Fischbach. |
| 14 | 1.000 | 0.391 | cut | User's next steps for Dynamic Website Optimization include debugging integration issues with Redis, assessing load time improvements using test cases, scaling the implementation for different user loads, and preparing documentation to share findings with their team. |
| 15 | 1.000 | 0.381 | cut | User was suggested to discuss assigning an internal codename for the Dynamic Website Optimization project with Jonas Albrecht or Elif Kaya to streamline communication. |
| 16 | 1.000 | 0.378 | cut | Alex Carter gets their coffee beans from Cinderbean. |
| 17 | 1.000 | 0.370 | cut | User needs to see Dr. Okafor for a confidential follow-up appointment. |
| 18 | 1.000 | 0.370 | cut | Alex Carter's terminal font is set to Monospace. |
| 19 | 1.000 | 0.367 | cut | Alex Carter prefers to use Visual Studio Code, Docker, Git, and Postman for development. |
| 20 | 1.000 | 0.356 | cut | User is working on Dynamic Website Optimization and is currently experimenting with caching mechanisms using Flask and Redis. Their goals include improving website load times, ensuring caching implementation reduces server load, evaluating the scalability of the caching solution, and documenting all results for future reference. |
| 21 | 1.000 | 0.353 | cut | User is facing a blocker in integrating Redis with their existing Flask application while working on Dynamic Website Optimization. |
| 22 | 1.000 | 0.352 | cut | User was recommended potential codenames for the Dynamic Website Optimization project, including 'SpeedBoost,' 'CacheMaster,' and 'LoadLight,' reflecting optimization and caching themes. |
| 23 | 1.000 | 0.336 | cut | Alex Carter uses the Solarized color theme in their editor. |
| 24 | 1.000 | 0.314 | cut | Alex Carter's preferred programming language is Python. |
| 25 | 1.000 | 0.308 | cut | Alex Carter prefers formal responses in communication. |
| 26 | 0.936 | 0.532 | cut | User was suggested to check the project repository, team's communication channels like Slack or Microsoft Teams, or the project's issue tracker to identify team members or pairing arrangements for the Dynamic Website Optimization project. |
| 27 | 0.519 | 0.741 | cut | User's team is having its offsite in Utrecht. |

**User 2, recall** (`u002-p3-recall`): "Which room is my weekly team
sync in?", expected Larch; failed. 24 rows in the store.

Target row: rank 24 of 24, Mem0 score 0.481, cosine 0.760 (rank 1 by
cosine): "User's team holds their weekly sync meetings in the Larch
room"

| Rank | Score | Cosine | Seen | Row |
|---:|---:|---:|---|---|
| 1 | 1.000 | 0.485 | in block | User attends their book club gatherings at Bookhaven |
| 2 | 1.000 | 0.482 | in block | Elena Martinez spends her weekends playing Wingspan with her friends. |
| 3 | 1.000 | 0.455 | in block | User is focused on optimizing the Data Analysis Pipeline project for Vantrell Aerospace, which includes tasks such as investigating memory management solutions for Python, testing the pipeline's performance on diverse data sizes, and documenting optimization steps. |
| 4 | 1.000 | 0.448 | in block | User is working on the Data Analysis Pipeline project for Vantrell Aerospace. |
| 5 | 1.000 | 0.433 | in block | User works with DuckDB for storing service information. |
| 6 | 1.000 | 0.431 | in block | User's work is monitored using Taiga. |
| 7 | 1.000 | 0.426 | in block | User's name is Elena Martinez. |
| 8 | 1.000 | 0.420 | in block | User is facing unexpected memory issues during parallel processing as a blocker in their Data Analysis Pipeline project. |
| 9 | 1.000 | 0.417 | in block | User's Data Analysis Pipeline project stores service information in DuckDB. |
| 10 | 1.000 | 0.411 | in block | User's Data Analysis Pipeline project is being developed for Vantrell Aerospace. |
| 11 | 1.000 | 0.409 | cut | User's next steps for their Data Analysis Pipeline project include investigating memory management solutions for Python, testing pipeline performance on diverse data sizes, and documenting steps taken to optimize the code. |
| 12 | 1.000 | 0.406 | cut | Elena Martinez is working on a project for a client named Halcyon Robotics. |
| 13 | 1.000 | 0.403 | cut | Elena Martinez prefers to use Visual Studio Code, Docker, and GitHub for development. |
| 14 | 1.000 | 0.391 | cut | Elena Martinez's preferred programming language is Python. |
| 15 | 1.000 | 0.386 | cut | Elena Martinez is working on a startup named Thistledown as a side project and has requested to keep this information private. |
| 16 | 1.000 | 0.375 | cut | User is working on a Data Analysis Pipeline and is currently optimizing Python scripts for parallel processing. Their goals include improving data processing speed by 30%, ensuring compatibility with large datasets, and developing robust error handling in the pipeline. |
| 17 | 1.000 | 0.375 | cut | User's Data Analysis Pipeline project stores confidential information in Akeyless. |
| 18 | 1.000 | 0.359 | cut | Elena Martinez likes detailed responses. |
| 19 | 1.000 | 0.351 | cut | User's Data Analysis Pipeline project uses Buildkite for continuous integration (CI). |
| 20 | 0.993 | 0.503 | cut | Elena Martinez uses Ryver to chat with her team. |
| 21 | 0.923 | 0.539 | cut | User mentioned using Brosix for team chats and Visual Studio Code for development. |
| 22 | 0.919 | 0.541 | cut | User enjoys playing Wingspan with friends on weekends as a hobby. |
| 23 | 0.843 | 0.579 | cut | Elena Martinez's team chat has been moved to Brosix. |

**User 2, recency** (`u002-p4-recency`): "Which chat app does my team
use?", expected Brosix, stale Ryver; failed. 25 rows in the store.

Target row: rank 25 of 25, Mem0 score 0.638, cosine 0.681 (rank 1 by
cosine): "Elena Martinez's team chat has been moved to Brosix."

| Rank | Score | Cosine | Seen | Row |
|---:|---:|---:|---|---|
| 1 | 1.000 | 0.495 | in block | User enjoys playing Wingspan with friends on weekends as a hobby. |
| 2 | 1.000 | 0.487 | in block | User's name is Elena Martinez. |
| 3 | 1.000 | 0.481 | in block | Elena Martinez prefers to use Visual Studio Code, Docker, and GitHub for development. |
| 4 | 1.000 | 0.473 | in block | User is working on the Data Analysis Pipeline project for Vantrell Aerospace. |
| 5 | 1.000 | 0.471 | in block | User works with DuckDB for storing service information. |
| 6 | 1.000 | 0.469 | in block | User is focused on optimizing the Data Analysis Pipeline project for Vantrell Aerospace, which includes tasks such as investigating memory management solutions for Python, testing the pipeline's performance on diverse data sizes, and documenting optimization steps. |
| 7 | 1.000 | 0.468 | in block | User's work is monitored using Taiga. |
| 8 | 1.000 | 0.464 | in block | User's Data Analysis Pipeline project stores service information in DuckDB. |
| 9 | 1.000 | 0.464 | in block | Elena Martinez is working on a project for a client named Halcyon Robotics. |
| 10 | 1.000 | 0.457 | in block | Elena Martinez's preferred programming language is Python. |
| 11 | 1.000 | 0.456 | cut | Elena Martinez spends her weekends playing Wingspan with her friends. |
| 12 | 1.000 | 0.455 | cut | Elena Martinez is working on a startup named Thistledown as a side project and has requested to keep this information private. |
| 13 | 1.000 | 0.455 | cut | User's Data Analysis Pipeline project is being developed for Vantrell Aerospace. |
| 14 | 1.000 | 0.451 | cut | User attends their book club gatherings at Bookhaven |
| 15 | 1.000 | 0.440 | cut | User's Data Analysis Pipeline project stores confidential information in Akeyless. |
| 16 | 1.000 | 0.434 | cut | User's Data Analysis Pipeline project uses Buildkite for continuous integration (CI). |
| 17 | 1.000 | 0.429 | cut | User's next steps for their Data Analysis Pipeline project include investigating memory management solutions for Python, testing pipeline performance on diverse data sizes, and documenting steps taken to optimize the code. |
| 18 | 1.000 | 0.421 | cut | Elena Martinez likes detailed responses. |
| 19 | 1.000 | 0.401 | cut | User is working on a Data Analysis Pipeline and is currently optimizing Python scripts for parallel processing. Their goals include improving data processing speed by 30%, ensuring compatibility with large datasets, and developing robust error handling in the pipeline. |
| 20 | 1.000 | 0.376 | cut | User is facing unexpected memory issues during parallel processing as a blocker in their Data Analysis Pipeline project. |
| 21 | 0.883 | 0.558 | cut | User's team holds their weekly sync meetings in the Larch room |
| 22 | 0.811 | 0.595 | cut | User's weekly team sync details, including the room or virtual meeting link, are typically recorded in the Taiga project management tool. |
| 23 | 0.698 | 0.651 | cut | Elena Martinez uses Ryver to chat with her team. |
| 24 | 0.657 | 0.671 | cut | User mentioned using Brosix for team chats and Visual Studio Code for development. |

**User 3, recall** (`u003-p3-recall`): "Which city do I live in?",
expected Uppsala; failed. 29 rows in the store.

Target row: rank 29 of 29, Mem0 score 0.907, cosine 0.546 (rank 1 by
cosine): "User's home is in Uppsala."

| Rank | Score | Cosine | Seen | Row |
|---:|---:|---:|---|---|
| 1 | 1.000 | 0.466 | in block | User's name is Jordan Michaels. |
| 2 | 1.000 | 0.437 | in block | User is a member of the Lyrebird choir and sings with them. |
| 3 | 1.000 | 0.432 | in block | User prefers to use GitHub, Visual Studio Code, and Postman for development. |
| 4 | 1.000 | 0.424 | in block | User is giving a presentation at Fjordstack, which is the only conference where they are presenting. |
| 5 | 1.000 | 0.418 | in block | User's preferred programming language is JavaScript. |
| 6 | 1.000 | 0.417 | in block | User has a yoga session scheduled at the Lotusgate studio on November 9, 2026. |
| 7 | 1.000 | 0.411 | in block | User attends a running club that gathers in Wychwood Park. |
| 8 | 1.000 | 0.403 | in block | User is giving a presentation at Fjordstack in December 2026 and is currently focused on the Dynamic Form Builder project. |
| 9 | 1.000 | 0.400 | in block | User attends book club gatherings at Bookhaven. |
| 10 | 1.000 | 0.391 | in block | User spends weekends playing Carcassonne with their friends. |
| 11 | 1.000 | 0.389 | cut | User uses the Halmak layout for typing on their keyboard. |
| 12 | 1.000 | 0.387 | cut | User's staging server for deployment was relocated to wren-04 on November 9, 2026. |
| 13 | 1.000 | 0.370 | cut | The talk 'Real-Time Analytics for Dynamic Form Builder' will cover tools and techniques for real-time data collection, analysis, and visualization to optimize performance for real-time form rendering. |
| 14 | 1.000 | 0.368 | cut | User likes concise responses. |
| 15 | 1.000 | 0.367 | cut | User is working on a Dynamic Form Builder project and is currently experimenting with testing dynamic field rendering based on user inputs. |
| 16 | 1.000 | 0.366 | cut | User uses the avocet-06 staging server for deployment in their Dynamic Form Builder project. |
| 17 | 1.000 | 0.356 | cut | User volunteers at the Stonebridge food bank. |
| 18 | 1.000 | 0.352 | cut | User's goals for the Dynamic Form Builder project include developing a reusable component for dynamic form creation, ensuring seamless integration with backend APIs, and optimizing performance for real-time form rendering. |
| 19 | 1.000 | 0.350 | cut | User will be giving a presentation at Kernelcon in December 2026. |
| 20 | 1.000 | 0.340 | cut | User's next steps for the Dynamic Form Builder project are to refactor the dynamic rendering logic using React hooks, investigate and address API latency issues, and write unit tests for form validation rules. |
| 21 | 1.000 | 0.335 | cut | User's company is having preliminary discussions about being bought by Gannet Systems. |
| 22 | 1.000 | 0.334 | cut | User gets their coffee beans from Hollowpeak. |
| 23 | 1.000 | 0.333 | cut | User was recommended the following acquisition talks relevant to their Dynamic Form Builder project: 'Scaling User Acquisition with Data-Driven Strategies', 'User-Centric Acquisition: Building Trust and Engagement', 'Leveraging APIs for Seamless Integration and User Acquisition', and 'Real-Time Analytics for Dynamic Form Builder'. |
| 24 | 1.000 | 0.324 | cut | User sends their logs to Logtail for the Dynamic Form Builder project |
| 25 | 1.000 | 0.318 | cut | The talk 'User-Centric Acquisition: Building Trust and Engagement' will focus on creating engaging content, designing intuitive user interfaces, and fostering a community around a product or service. |
| 26 | 1.000 | 0.299 | cut | The talk 'Leveraging APIs for Seamless Integration and User Acquisition' will explore best practices for API design, security, and performance optimization to enhance user experience and drive acquisition. |
| 27 | 1.000 | 0.296 | cut | The talk 'Scaling User Acquisition with Data-Driven Strategies' will cover data analytics, A/B testing, user segmentation, and leveraging social media and SEO for effective user acquisition. |
| 28 | 1.000 | 0.294 | cut | User's blockers for the Dynamic Form Builder project include intermittent API response delays. |

**User 3, recency** (`u003-p4-recency`): "Which staging server do we
deploy to?", expected wren-04, stale avocet-06; failed. 29 rows in the
store.

Target row: rank 29 of 29, Mem0 score 0.535, cosine 0.733 (rank 1 by
cosine): "User's staging server for deployment was relocated to wren-04
on November 9, 2026."

| Rank | Score | Cosine | Seen | Row |
|---:|---:|---:|---|---|
| 1 | 1.000 | 0.486 | in block | User prefers to use GitHub, Visual Studio Code, and Postman for development. |
| 2 | 1.000 | 0.480 | in block | User's home is in Uppsala. |
| 3 | 1.000 | 0.469 | in block | User is giving a presentation at Fjordstack in December 2026 and is currently focused on the Dynamic Form Builder project. |
| 4 | 1.000 | 0.457 | hidden | User's company is having preliminary discussions about being bought by Gannet Systems. |
| 5 | 1.000 | 0.453 | in block | User has a yoga session scheduled at the Lotusgate studio on November 9, 2026. |
| 6 | 1.000 | 0.451 | in block | User's next steps for the Dynamic Form Builder project are to refactor the dynamic rendering logic using React hooks, investigate and address API latency issues, and write unit tests for form validation rules. |
| 7 | 1.000 | 0.445 | in block | User is a member of the Lyrebird choir and sings with them. |
| 8 | 1.000 | 0.445 | in block | The talk 'Leveraging APIs for Seamless Integration and User Acquisition' will explore best practices for API design, security, and performance optimization to enhance user experience and drive acquisition. |
| 9 | 1.000 | 0.432 | in block | User is working on a Dynamic Form Builder project and is currently experimenting with testing dynamic field rendering based on user inputs. |
| 10 | 1.000 | 0.421 | in block | The talk 'Real-Time Analytics for Dynamic Form Builder' will cover tools and techniques for real-time data collection, analysis, and visualization to optimize performance for real-time form rendering. |
| 11 | 1.000 | 0.417 | cut | The talk 'Scaling User Acquisition with Data-Driven Strategies' will cover data analytics, A/B testing, user segmentation, and leveraging social media and SEO for effective user acquisition. |
| 12 | 1.000 | 0.415 | cut | User will be giving a presentation at Kernelcon in December 2026. |
| 13 | 1.000 | 0.409 | cut | User's goals for the Dynamic Form Builder project include developing a reusable component for dynamic form creation, ensuring seamless integration with backend APIs, and optimizing performance for real-time form rendering. |
| 14 | 1.000 | 0.399 | cut | The talk 'User-Centric Acquisition: Building Trust and Engagement' will focus on creating engaging content, designing intuitive user interfaces, and fostering a community around a product or service. |
| 15 | 1.000 | 0.398 | cut | User's name is Jordan Michaels. |
| 16 | 1.000 | 0.393 | cut | User volunteers at the Stonebridge food bank. |
| 17 | 1.000 | 0.391 | cut | User's blockers for the Dynamic Form Builder project include intermittent API response delays. |
| 18 | 1.000 | 0.388 | cut | User was recommended the following acquisition talks relevant to their Dynamic Form Builder project: 'Scaling User Acquisition with Data-Driven Strategies', 'User-Centric Acquisition: Building Trust and Engagement', 'Leveraging APIs for Seamless Integration and User Acquisition', and 'Real-Time Analytics for Dynamic Form Builder'. |
| 19 | 1.000 | 0.387 | cut | User gets their coffee beans from Hollowpeak. |
| 20 | 1.000 | 0.386 | cut | User's preferred programming language is JavaScript. |
| 21 | 1.000 | 0.384 | cut | User uses the Halmak layout for typing on their keyboard. |
| 22 | 1.000 | 0.383 | cut | User spends weekends playing Carcassonne with their friends. |
| 23 | 1.000 | 0.383 | cut | User sends their logs to Logtail for the Dynamic Form Builder project |
| 24 | 1.000 | 0.348 | cut | User attends a running club that gathers in Wychwood Park. |
| 25 | 1.000 | 0.337 | cut | User attends book club gatherings at Bookhaven. |
| 26 | 1.000 | 0.328 | cut | User likes concise responses. |
| 27 | 0.996 | 0.502 | cut | User is giving a presentation at Fjordstack, which is the only conference where they are presenting. |
| 28 | 0.652 | 0.674 | cut | User uses the avocet-06 staging server for deployment in their Dynamic Form Builder project. |

**User 4, recall** (`u004-p3-recall`): "Who is the client for my current
project?", expected Gannet Systems; failed. 29 rows in the store.

Target row: rank 27 of 29, Mem0 score 0.817, cosine 0.592 (rank 3 by
cosine): "User is developing the SmartWeather project for Gannet
Systems."

| Rank | Score | Cosine | Seen | Row |
|---:|---:|---:|---|---|
| 1 | 1.000 | 0.498 | in block | User is enrolled in a nighttime class for calligraphy. |
| 2 | 1.000 | 0.488 | in block | Michael Peterson's preferred programming language is Python. |
| 3 | 1.000 | 0.480 | in block | User lives in Dunedin. |
| 4 | 1.000 | 0.467 | in block | User's weekly team sync is held in the Saffron room. |
| 5 | 1.000 | 0.456 | in block | User's weekly team sync has been relocated to the Larch room. |
| 6 | 1.000 | 0.451 | in block | Michael Peterson's home is in Leuven. |
| 7 | 1.000 | 0.446 | in block | User helps out at the Maplewood food bank. |
| 8 | 1.000 | 0.432 | in block | Michael Peterson prefers using Elvish as his shell. |
| 9 | 1.000 | 0.415 | in block | User attends running club gatherings in Larkfield Park. |
| 10 | 1.000 | 0.405 | in block | Michael Peterson goes swimming at Kingsmere. |
| 11 | 1.000 | 0.402 | cut | Michael Peterson gets his coffee beans from Mossgrove. |
| 12 | 1.000 | 0.378 | cut | Michael Peterson uses the Engram keyboard layout for typing. |
| 13 | 1.000 | 0.370 | cut | Michael Peterson prefers concise responses. |
| 14 | 0.993 | 0.503 | cut | User sends logs for the SmartWeather project to Papertrail for monitoring and analysis. |
| 15 | 0.978 | 0.511 | cut | User stores service information for the SmartWeather project in TimescaleDB. |
| 16 | 0.954 | 0.523 | cut | User's current blockers in the SmartWeather project include API inconsistencies in returned data formats. |
| 17 | 0.950 | 0.525 | cut | Michael Peterson prefers to use Visual Studio Code, JIRA, and Docker for development. |
| 18 | 0.944 | 0.528 | cut | User is working on SmartWeather, focusing on testing machine learning-based predictive models for hourly rainfall. Their goals include optimizing the accuracy of rainfall predictions, integrating real-time weather data APIs, and refining the model for lower latency calculations. |
| 19 | 0.931 | 0.535 | cut | User's issues in the SmartWeather project are sent to Rollbar for tracking and resolution. |
| 20 | 0.908 | 0.546 | cut | User's name is Michael Peterson. |
| 21 | 0.906 | 0.547 | cut | User's next steps for the SmartWeather project are analyzing model performance with historical weather data, resolving API inconsistencies through better exception handling, deploying the trial version for internal testing with real-time data, and documenting findings for stakeholder review. |
| 22 | 0.905 | 0.547 | cut | User's next steps for the SmartWeather project include analyzing model performance using tools like Jupyter Notebook, Pandas, and Scikit-learn, resolving API inconsistencies with tools like Postman and Rollbar, deploying a trial version for internal testing with real-time data, and documenting findings using tools like Confluence or Google Docs for stakeholder review. |
| 23 | 0.902 | 0.549 | cut | User's next steps for the SmartWeather project include analyzing model performance, deploying a trial version for internal testing, and documenting findings for stakeholder review. |
| 24 | 0.890 | 0.555 | cut | User's current project, SmartWeather, has API inconsistencies that need to be resolved through better exception handling and data validation processes. |
| 25 | 0.875 | 0.562 | cut | User is scheduled for a pairing session with Greta Sandvik during the week of November 9, 2026. |
| 26 | 0.819 | 0.590 | cut | User is meeting their lawyer, Ewan Calloway, in December 2026 and has requested this information to remain private. |

**User 4, recency** (`u004-p4-recency`): "Which room is my weekly team
sync in?", expected Larch, stale Saffron; failed. 29 rows in the store.

Target row: rank 28 of 29, Mem0 score 0.303, cosine 0.849 (rank 2 by
cosine): "User's weekly team sync has been relocated to the Larch room."

| Rank | Score | Cosine | Seen | Row |
|---:|---:|---:|---|---|
| 1 | 1.000 | 0.494 | in block | User is enrolled in a nighttime class for calligraphy. |
| 2 | 1.000 | 0.458 | in block | User's name is Michael Peterson and they are working on the SmartWeather project for Gannet Systems, which involves analyzing model performance with historical weather data, resolving API inconsistencies through better exception handling, deploying a trial version for internal testing with real-time data, and documenting findings for stakeholder review. |
| 3 | 1.000 | 0.455 | in block | User's issues in the SmartWeather project are sent to Rollbar for tracking and resolution. |
| 4 | 1.000 | 0.452 | in block | Michael Peterson uses the Engram keyboard layout for typing. |
| 5 | 1.000 | 0.447 | in block | User is developing the SmartWeather project for Gannet Systems. |
| 6 | 1.000 | 0.445 | in block | User is working on the SmartWeather project, which involves tasks such as analyzing model performance with historical weather data, resolving API inconsistencies through better exception handling, deploying a trial version for internal testing with real-time data, and documenting findings for stakeholder review. |
| 7 | 1.000 | 0.443 | in block | User's name is Michael Peterson. |
| 8 | 1.000 | 0.440 | in block | User stores service information for the SmartWeather project in TimescaleDB. |
| 9 | 1.000 | 0.440 | in block | User is working on SmartWeather, focusing on testing machine learning-based predictive models for hourly rainfall. Their goals include optimizing the accuracy of rainfall predictions, integrating real-time weather data APIs, and refining the model for lower latency calculations. |
| 10 | 1.000 | 0.437 | in block | Michael Peterson's home is in Leuven. |
| 11 | 1.000 | 0.431 | cut | User lives in Dunedin. |
| 12 | 1.000 | 0.426 | cut | User's next steps for the SmartWeather project include analyzing model performance using tools like Jupyter Notebook, Pandas, and Scikit-learn, resolving API inconsistencies with tools like Postman and Rollbar, deploying a trial version for internal testing with real-time data, and documenting findings using tools like Confluence or Google Docs for stakeholder review. |
| 13 | 1.000 | 0.426 | cut | Michael Peterson prefers to use Visual Studio Code, JIRA, and Docker for development. |
| 14 | 1.000 | 0.426 | cut | User's next steps for the SmartWeather project are analyzing model performance with historical weather data, resolving API inconsistencies through better exception handling, deploying the trial version for internal testing with real-time data, and documenting findings for stakeholder review. |
| 15 | 1.000 | 0.425 | cut | User helps out at the Maplewood food bank. |
| 16 | 1.000 | 0.423 | cut | User's current blockers in the SmartWeather project include API inconsistencies in returned data formats. |
| 17 | 1.000 | 0.411 | cut | User's next steps for the SmartWeather project include analyzing model performance, deploying a trial version for internal testing, and documenting findings for stakeholder review. |
| 18 | 1.000 | 0.404 | cut | User sends logs for the SmartWeather project to Papertrail for monitoring and analysis. |
| 19 | 1.000 | 0.399 | cut | User's current project, SmartWeather, has API inconsistencies that need to be resolved through better exception handling and data validation processes. |
| 20 | 1.000 | 0.397 | cut | Michael Peterson's preferred programming language is Python. |
| 21 | 1.000 | 0.391 | cut | Michael Peterson gets his coffee beans from Mossgrove. |
| 22 | 1.000 | 0.389 | cut | User is meeting their lawyer, Ewan Calloway, in December 2026 and has requested this information to remain private. |
| 23 | 1.000 | 0.371 | cut | Michael Peterson goes swimming at Kingsmere. |
| 24 | 1.000 | 0.348 | cut | Michael Peterson prefers concise responses. |
| 25 | 1.000 | 0.328 | cut | Michael Peterson prefers using Elvish as his shell. |
| 26 | 0.999 | 0.501 | cut | User attends running club gatherings in Larkfield Park. |
| 27 | 0.933 | 0.534 | cut | User is scheduled for a pairing session with Greta Sandvik during the week of November 9, 2026. |

