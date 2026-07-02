# ============================
# PWHL Daily Update Script
# Run this daily to update with new data only
# ============================

library(httr)
library(jsonlite)
library(dplyr)
library(purrr)
library(readr)
library(tibble)
library(stringr)
library(glue)
library(fastRhockey)

# ============================
# SETUP PATHS
# ============================

base_dir <- "PWHL"
data_dir <- file.path(base_dir, "data")

if (!dir.exists(data_dir)) {
  stop("Data directory not found! Please run initial_setup.R first.")
}

message("Checking for updates in: ", data_dir)

# ============================
# API CONFIGURATION
# ============================

base_url    <- "https://lscluster.hockeytech.com/feed/index.php"
api_key     <- "446521baf8c38984"
client_code <- "pwhl"

common_params <- list(
  feed        = "modulekit",
  key         = api_key,
  client_code = client_code
)

# readr guesses column types from the file's own values. Once enough real
# (non-blank) game_length/referee-number values accumulate, its heuristic can
# flip a column from <character> to <time>/<logical>, and bind_rows() then
# refuses to combine it with the freshly-fetched <character> data -- this is
# exactly what broke every run from 2026-04-25 onward. Pin the ambiguous
# columns explicitly so the guess can't drift out from under us.
game_summary_col_types <- cols(
  game_id              = col_character(),
  season_id            = col_character(),
  game_length          = col_character(),
  referee1_number      = col_character(),
  referee2_number      = col_character(),
  linesperson1_number  = col_character(),
  linesperson2_number  = col_character(),
  .default             = col_guess()
)

`%||%` <- function(x, y) if (!is.null(x)) x else y

scalar_chr <- function(x) {
  if (is.null(x) || length(x) == 0) return(NA_character_)
  if (is.data.frame(x)) x <- x[[1]]
  if (length(x) == 0) return(NA_character_)
  as.character(x[1])
}

# For wide, loosely-typed tables (many digit-only ID/flag columns): cast
# `old`'s shared columns to match `new`'s types before bind_rows(). Without
# this, a digit-only column written to CSV can silently round-trip back as
# <double> on the next read_csv() while the freshly-fetched data is
# <character> (or vice versa), and bind_rows() hard-errors on the mismatch.
align_col_types <- function(old, new) {
  for (col in intersect(names(old), names(new))) {
    target <- class(new[[col]])[1]
    if (!identical(class(old[[col]])[1], target)) {
      old[[col]] <- switch(target,
        character = as.character(old[[col]]),
        numeric   = suppressWarnings(as.numeric(old[[col]])),
        double    = suppressWarnings(as.double(old[[col]])),
        integer   = suppressWarnings(as.integer(old[[col]])),
        logical   = as.logical(old[[col]]),
        old[[col]]
      )
    }
  }
  old
}

# ============================
# HELPER FUNCTIONS (same as initial setup)
# ============================

parse_toi_to_seconds <- function(x) {
  sapply(x, function(val) {
    if (is.null(val) || is.na(val) || val == "") return(NA_real_)
    parts <- strsplit(as.character(val), ":", fixed = TRUE)[[1]]
    if (length(parts) == 2) {
      m <- suppressWarnings(as.numeric(parts[1]))
      s <- suppressWarnings(as.numeric(parts[2]))
      if (is.na(m) || is.na(s)) return(NA_real_)
      60 * m + s
    } else if (length(parts) == 3) {
      m <- suppressWarnings(as.numeric(parts[1]))
      s <- suppressWarnings(as.numeric(parts[2]))
      if (is.na(m) || is.na(s)) return(NA_real_)
      60 * m + s
    } else {
      NA_real_
    }
  })
}

clean_ice_time <- function(x) {
  vapply(x, function(val) {
    if (is.null(val) || is.na(val) || val == "") return(NA_character_)
    parts <- strsplit(as.character(val), ":", fixed = TRUE)[[1]]
    if (length(parts) == 2) {
      paste0(parts[1], ":", parts[2])
    } else if (length(parts) == 3) {
      paste0(parts[1], ":", parts[2])
    } else {
      NA_character_
    }
  }, character(1))
}

parse_game_length_to_seconds <- function(x) {
  sapply(x, function(val) {
    if (is.null(val) || is.na(val) || val == "") return(NA_real_)
    parts <- strsplit(as.character(val), ":", fixed = TRUE)[[1]]
    n <- length(parts)
    nums <- suppressWarnings(as.numeric(parts))
    if (any(is.na(nums))) return(NA_real_)

    if (n == 3) {
      h <- nums[1]; m <- nums[2]; s <- nums[3]
      h * 3600 + m * 60 + s
    } else if (n == 2) {
      a <- nums[1]; b <- nums[2]
      if (a <= 10 && b < 60) {
        a * 3600 + b * 60
      } else {
        a * 60 + b
      }
    } else {
      NA_real_
    }
  })
}

extract_officials <- function(gs) {
  out <- list(
    referee1_name = NA_character_, referee1_number = NA_character_,
    referee2_name = NA_character_, referee2_number = NA_character_,
    linesperson1_name = NA_character_, linesperson1_number = NA_character_,
    linesperson2_name = NA_character_, linesperson2_number = NA_character_
  )

  officials_on_ice <- gs$officialsOnIce %||% list()

  if (!is.null(officials_on_ice) && length(officials_on_ice) > 0) {
    df <- tryCatch(as_tibble(officials_on_ice), error = function(e) NULL)

    if (!is.null(df)) {
      desc_col <- if ("description" %in% names(df)) "description" else NA_character_
      jersey_col <- if ("jersey_number" %in% names(df)) {
        "jersey_number"
      } else if ("number" %in% names(df)) {
        "number"
      } else {
        NA_character_
      }

      df$full_name <- paste(df$first_name %||% "", df$last_name %||% "")

      if (!is.na(desc_col)) {
        refs  <- df %>% filter(grepl("ref", .data[[desc_col]], ignore.case = TRUE))
        lines <- df %>% filter(grepl("line", .data[[desc_col]], ignore.case = TRUE))

        if (nrow(refs) >= 1) {
          out$referee1_name <- refs$full_name[1]
          if (!is.na(jersey_col)) out$referee1_number <- scalar_chr(refs[[jersey_col]][1])
        }
        if (nrow(refs) >= 2) {
          out$referee2_name <- refs$full_name[2]
          if (!is.na(jersey_col)) out$referee2_number <- scalar_chr(refs[[jersey_col]][2])
        }

        if (nrow(lines) >= 1) {
          out$linesperson1_name <- lines$full_name[1]
          if (!is.na(jersey_col)) out$linesperson1_number <- scalar_chr(lines[[jersey_col]][1])
        }
        if (nrow(lines) >= 2) {
          out$linesperson2_name <- lines$full_name[2]
          if (!is.na(jersey_col)) out$linesperson2_number <- scalar_chr(lines[[jersey_col]][2])
        }
      }
    }
  }

  if (!is.null(gs$referee1)  && is.na(out$referee1_name))     out$referee1_name       <- gs$referee1
  if (!is.null(gs$referee2)  && is.na(out$referee2_name))     out$referee2_name       <- gs$referee2
  if (!is.null(gs$linesman1) && is.na(out$linesperson1_name)) out$linesperson1_name   <- gs$linesman1
  if (!is.null(gs$linesman2) && is.na(out$linesperson2_name)) out$linesperson2_name   <- gs$linesman2

  as_tibble_row(out)
}

get_players_list <- function(gs, side = c("home", "visitor")) {
  side <- match.arg(side)

  if (side == "home") {
    candidates <- c("home_team_lineup", "home_lineup", "home_roster")
  } else {
    candidates <- c("visiting_team_lineup", "visitor_team_lineup",
                    "visiting_lineup", "visitor_lineup",
                    "visiting_roster", "visitor_roster")
  }

  for (nm in candidates) {
    obj <- gs[[nm]]
    if (!is.null(obj) && !is.null(obj$players)) return(obj$players)
  }

  NULL
}

extract_lineup_players <- function(players_list, team_side, game_id, season_id) {
  if (is.null(players_list) || length(players_list) == 0) return(NULL)

  df <- NULL
  if (is.data.frame(players_list)) {
    df <- players_list
  } else if (is.list(players_list)) {
    df <- tryCatch(bind_rows(players_list), error = function(e) NULL)
  }
  if (is.null(df)) return(NULL)

  keep_cols <- intersect(c("person_id", "player_id"), names(df))
  if (length(keep_cols) == 0) return(NULL)

  out <- df[, keep_cols, drop = FALSE]

  if (!"person_id" %in% names(out)) out$person_id <- NA_character_
  if (!"player_id" %in% names(out)) out$player_id <- NA_character_

  out <- out %>%
    mutate(
      person_id = as.character(person_id),
      player_id = as.character(player_id)
    ) %>%
    mutate(
      person_id = ifelse(person_id == "" | is.na(person_id), NA_character_, person_id),
      player_id = ifelse(player_id == "" | is.na(player_id), NA_character_, player_id)
    ) %>%
    filter(!(is.na(person_id) & is.na(player_id)))

  if (nrow(out) == 0) return(NULL)

  out %>%
    mutate(
      game_id   = as.character(game_id),
      season_id = as.character(season_id),
      team_side = team_side
    ) %>%
    select(game_id, season_id, team_side, person_id, player_id)
}

fetch_game_details <- function(gid) {
  res <- GET(
    base_url,
    query = list(
      feed        = "gc",
      tab         = "gamesummary",
      game_id     = gid,
      key         = api_key,
      client_code = client_code,
      fmt         = "json"
    )
  )

  if (http_error(res)) return(NULL)

  txt <- content(res, as = "text", encoding = "UTF-8")
  js <- tryCatch(fromJSON(txt, simplifyVector = FALSE), error = function(e) NULL)
  
  if (is.null(js$GC) || is.null(js$GC$Gamesummary)) return(NULL)

  gs   <- js$GC$Gamesummary
  meta <- gs$meta %||% list()
  season_id <- scalar_chr(meta$season_id)

  home_team_name    <- gs$home$name    %||% NA_character_
  visitor_team_name <- gs$visitor$name %||% NA_character_
  home_goals    <- meta$home_goal_count     %||% meta$home_score    %||% NA
  visitor_goals <- meta$visiting_goal_count %||% meta$visitor_score %||% NA
  game_length_raw <- gs$game_length %||% meta$length %||% NA_character_

  game_row <- tibble(
    game_id             = as.character(gid),
    season_id           = season_id,
    game_date           = gs$game_date %||% meta$date_played %||% NA_character_,
    home_team           = home_team_name,
    visitor_team        = visitor_team_name,
    home_score          = suppressWarnings(as.integer(home_goals)),
    visitor_score       = suppressWarnings(as.integer(visitor_goals)),
    attendance          = suppressWarnings(as.integer(meta$attendance %||% NA)),
    game_length         = game_length_raw,
    game_length_seconds = parse_game_length_to_seconds(game_length_raw),
    venue               = gs$venue %||% NA_character_,
    num_periods         = suppressWarnings(as.integer(meta$number_of_periods %||% meta$periods %||% NA)),
    shootout_rounds     = suppressWarnings(as.integer(meta$shootout_rounds %||% meta$shootout %||% NA)),
    is_final            = identical(scalar_chr(meta$final), "1")
  )

  officials_df <- extract_officials(gs)
  home_players_list    <- get_players_list(gs, "home")
  visitor_players_list <- get_players_list(gs, "visitor")
  home_players_tbl    <- extract_lineup_players(home_players_list, "home", gid, season_id)
  visitor_players_tbl <- extract_lineup_players(visitor_players_list, "visitor", gid, season_id)
  players_tbl <- bind_rows(compact(list(home_players_tbl, visitor_players_tbl)))

  list(game = bind_cols(game_row, officials_df), players = players_tbl)
}

# ============================
# 1) CHECK FOR NEW GAMES
# ============================

message("\n=== Checking for New Games ===")

# A game_id can show up in the schedule months before it's actually played --
# PWHL publishes the full season schedule upfront. So "new" can't mean
# "game_id not seen before"; it has to mean "final/played game whose summary
# we either don't have yet, or only have as a pre-game placeholder (fetched
# before the game was actually final -- home_score/visitor_score stuck at 0,
# no officials, no attendance)". Track completion state against
# pwhl_game_summaries.csv's own is_final flag, not the schedule file.
existing_summaries_raw <- read_csv(file.path(data_dir, "pwhl_game_summaries.csv"),
                                    col_types = game_summary_col_types) %>%
  mutate(
    season_id = as.character(season_id),
    game_id = as.character(game_id)
  )
if (!"is_final" %in% names(existing_summaries_raw)) {
  existing_summaries_raw$is_final <- FALSE
}
existing_final_ids <- existing_summaries_raw %>%
  filter(is_final %in% TRUE) %>%
  distinct(season_id, game_id)

# Get current schedule for all seasons
all_seasons <- tibble()
for (sid in 1:20) {
  res <- GET(base_url, query = c(common_params, list(view = "schedule", season_id = sid)))
  if (http_error(res)) next

  txt <- content(res, as = "text", encoding = "UTF-8")
  js <- tryCatch(fromJSON(txt, flatten = TRUE), error = function(e) NULL)

  if (!is.null(js$SiteKit$Schedule) && length(js$SiteKit$Schedule) > 0) {
    all_seasons <- bind_rows(all_seasons, tibble(season_id = sid))
  }
  Sys.sleep(0.3)
}

fetch_schedule_for_season <- function(sid) {
  res <- GET(base_url, query = c(common_params, list(view = "schedule", season_id = sid)))
  if (http_error(res)) return(NULL)

  txt <- content(res, as = "text", encoding = "UTF-8")
  js <- tryCatch(fromJSON(txt, flatten = TRUE), error = function(e) NULL)
  if (is.null(js$SiteKit$Schedule)) return(NULL)

  sched_df <- as_tibble(js$SiteKit$Schedule)
  sched_df %>% mutate(season_id = as.character(sid))
}

all_games <- map_dfr(all_seasons$season_id, fetch_schedule_for_season)

# Keep the full schedule (with played/final status) so future runs can tell
# which already-known game_ids are actually done, not just which exist.
current_games <- all_games %>%
  mutate(
    game_id = as.character(game_id),
    is_final = final == "1" | grepl("^final", game_status, ignore.case = TRUE)
  ) %>%
  select(season_id, game_id, date_played, game_status, is_final)

write_csv(current_games, file.path(data_dir, "pwhl_season_game_ids.csv"))

# Find new (final, not-yet-properly-summarized) games
new_games <- current_games %>%
  filter(is_final) %>%
  select(season_id, game_id) %>%
  anti_join(existing_final_ids, by = c("season_id", "game_id"))

if (nrow(new_games) == 0) {
  message("  ✓ No new completed games found")
} else {
  message("  ✓ Found ", nrow(new_games), " new completed game(s)")
}

# ============================
# 2) UPDATE GAME SUMMARIES & PLAYERS
# ============================

if (nrow(new_games) > 0) {
  message("\n=== Updating Game Summaries ===")
  
  new_game_details <- map(new_games$game_id, function(gid) {
    message("  Fetching game ", gid)
    result <- fetch_game_details(gid)
    Sys.sleep(0.3)
    result
  })
  
  new_game_summaries <- new_game_details %>% map("game") %>% compact() %>% bind_rows()
  new_game_players <- new_game_details %>% map("players") %>% compact() %>% bind_rows()
  
  if (nrow(new_game_summaries) > 0) {
    existing_summaries <- read_csv(file.path(data_dir, "pwhl_game_summaries.csv"),
                                   col_types = game_summary_col_types) %>%
      mutate(game_id = as.character(game_id), season_id = as.character(season_id))
    # Upsert by game_id: a game may already have a pre-game placeholder row
    # (fetched before it was final) that this refetch should replace, not duplicate.
    updated_summaries <- existing_summaries %>%
      anti_join(new_game_summaries, by = c("season_id", "game_id")) %>%
      align_col_types(new_game_summaries) %>%
      bind_rows(new_game_summaries)
    write_csv(updated_summaries, file.path(data_dir, "pwhl_game_summaries.csv"))
    message("  ✓ Updated ", nrow(new_game_summaries), " game summaries")
  }

  if (nrow(new_game_players) > 0) {
    existing_players <- read_csv(file.path(data_dir, "pwhl_game_players.csv"),
                                 show_col_types = FALSE) %>%
      mutate(
        game_id = as.character(game_id),
        season_id = as.character(season_id),
        person_id = as.character(person_id),
        player_id = as.character(player_id)
      )
    updated_players <- existing_players %>%
      anti_join(new_game_players, by = c("season_id", "game_id")) %>%
      align_col_types(new_game_players) %>%
      bind_rows(new_game_players)
    write_csv(updated_players, file.path(data_dir, "pwhl_game_players.csv"))
    message("  ✓ Updated ", nrow(new_game_players), " game player records")
  }
}

# ============================
# 3) UPDATE PLAYER GAME LOGS
# ============================

message("\n=== Updating Player Game Logs ===")

# Determine which players need a log refresh by comparing actual roster
# appearances (pwhl_game_players.csv, which section 2 keeps complete for
# every final game) against what's already logged -- not by reusing
# new_games/new_game_players. Those only cover *this run's* newly-final
# games, so once summaries catch up, new_games goes to zero forever and a
# player log gap from an earlier crashed run would never get retried.
all_game_players <- read_csv(file.path(data_dir, "pwhl_game_players.csv"), show_col_types = FALSE) %>%
  mutate(
    season_id = as.character(season_id),
    game_id = as.character(game_id),
    player_id = as.character(player_id)
  ) %>%
  filter(!is.na(player_id))

existing_log_appearances <- read_csv(file.path(data_dir, "pwhl_player_game_logs.csv"), show_col_types = FALSE) %>%
  mutate(
    season_id = as.character(season_id),
    game_id = as.character(game_id),
    player_id = as.character(player_id)
  ) %>%
  select(-any_of("id")) %>%
  distinct(season_id, player_id, game_id)

new_player_list <- all_game_players %>%
  distinct(season_id, player_id, game_id) %>%
  anti_join(existing_log_appearances, by = c("season_id", "player_id", "game_id")) %>%
  distinct(season_id, player_id)

{
  fetch_player_game_log <- function(season_id, player_id) {
    res <- GET(base_url, query = c(common_params, list(
      view = "player", category = "gamebygame", season_id = season_id, player_id = player_id
    )))

    if (http_error(res)) return(NULL)

    txt <- content(res, as = "text", encoding = "UTF-8")
    js <- tryCatch(fromJSON(txt, flatten = TRUE), error = function(e) NULL)
    
    games <- js$SiteKit$Player$games
    if (is.null(games) || length(games) == 0) return(NULL)

    df <- tryCatch(as_tibble(games), error = function(e) NULL)
    if (is.null(df) || nrow(df) == 0) return(NULL)

    num_cols <- c("goals", "assists", "points", "plus_minus", "plusminus", "shots", "hits", 
                  "shots_blocked_by_player", "penalty_minutes", "faceoffs_taken", "faceoffs_won",
                  "power_play_goals", "short_handed_goals", "empty_net_goals", "insurange_goals",
                  "game_winning_goals", "first_goals_scored", "game_tieing_goals",
                  "shootout_goals", "shootout_attempts", "shootout_shots",
                  "shootout_shots_percentage", "shooting_percentage")
    num_cols <- intersect(num_cols, names(df))
    if (length(num_cols) > 0) {
      df <- df %>% mutate(across(all_of(num_cols), ~ suppressWarnings(as.numeric(as.character(.)))))
    }

    if ("ice_time_minutes_seconds" %in% names(df)) {
      df <- df %>%
        mutate(
          ice_time_seconds = parse_toi_to_seconds(ice_time_minutes_seconds),
          ice_time_minutes_seconds = clean_ice_time(ice_time_minutes_seconds)
        )
    }

    if (!"id" %in% names(df)) return(NULL)

    # Drop the raw `id` column once game_id captures it as character --
    # keeping both around is how a digit-only column silently drifts back to
    # <double> on the next read_csv() and blows up bind_rows() (as it just did).
    df %>%
      mutate(season_id = as.character(season_id), player_id = as.character(player_id), game_id = as.character(id)) %>%
      select(-id)
  }
  
  if (nrow(new_player_list) > 0) {
    # Fetch updated logs for affected players
    updated_logs <- map2_dfr(new_player_list$season_id, new_player_list$player_id, 
                             function(sid, pid) {
      result <- fetch_player_game_log(sid, pid)
      Sys.sleep(0.2)
      result
    })
    
    if (nrow(updated_logs) > 0) {
      existing_logs <- read_csv(file.path(data_dir, "pwhl_player_game_logs.csv"),
                                show_col_types = FALSE) %>%
        mutate(game_id = as.character(game_id), season_id = as.character(season_id),
               player_id = as.character(player_id)) %>%
        select(-any_of("id"))
      
      # Remove old entries for updated players, then add new data
      final_logs <- existing_logs %>%
        anti_join(new_player_list, by = c("season_id", "player_id")) %>%
        align_col_types(updated_logs) %>%
        bind_rows(updated_logs)
      
      write_csv(final_logs, file.path(data_dir, "pwhl_player_game_logs.csv"))
      message("  ✓ Updated logs for ", nrow(new_player_list), " players")
    }
  } else {
    message("  ✓ No player game logs missing")
  }
}

# ============================
# 4) UPDATE PLAYER INFO (for new players only)
# ============================

message("\n=== Checking for New Players ===")

existing_players_info <- read_csv(file.path(data_dir, "pwhl_players_info.csv"),
                                 show_col_types = FALSE) %>%
  mutate(player_id = as.character(player_id), jersey_number = as.character(jersey_number))

# Same reasoning as section 3: check against every known roster appearance,
# not just today's new_game_players, so a profile gap from an earlier
# crashed run still gets caught up once summaries stop finding anything new.
{
  new_player_ids <- all_game_players %>%
    distinct(player_id) %>%
    anti_join(existing_players_info, by = "player_id")

  if (nrow(new_player_ids) > 0) {
    message("  ✓ Found ", nrow(new_player_ids), " new player(s)")
    
    fetch_player_profile <- function(player_id) {
      res <- GET(base_url, query = c(common_params, list(
        view = "player", category = "profile", player_id = player_id
      )))

      if (http_error(res)) return(NULL)

      txt <- content(res, as = "text", encoding = "UTF-8")
      js <- tryCatch(fromJSON(txt, flatten = TRUE), error = function(e) NULL)
      
      if (is.null(js$SiteKit$Player)) return(NULL)
      
      player <- js$SiteKit$Player
      
      birthplace_parts <- c(
        if (!is.null(player$birthtown) && player$birthtown != "") player$birthtown else NULL,
        if (!is.null(player$birthprov) && player$birthprov != "") player$birthprov else NULL,
        if (!is.null(player$birthcntry) && player$birthcntry != "") player$birthcntry else NULL
      )
      birthplace <- if (length(birthplace_parts) > 0) paste(birthplace_parts, collapse = ", ") else NA_character_
      
      height_clean <- if (!is.null(player$height)) gsub("\\\\", "", player$height) else NA_character_
      
      tibble(
        player_id = as.character(player_id),
        first_name = player$first_name %||% NA_character_,
        last_name = player$last_name %||% NA_character_,
        player_name = player$name %||% paste(player$first_name %||% "", player$last_name %||% ""),
        jersey_number = as.character(player$jersey_number %||% NA),
        position = player$position %||% NA_character_,
        date_of_birth = player$birthdate %||% NA_character_,
        birthplace = birthplace,
        hometown = player$hometown %||% NA_character_,
        nationality = player$birthcntry %||% NA_character_,
        height = height_clean,
        shoots = player$shoots %||% NA_character_,
        catches = player$catches %||% NA_character_,
        primary_image = player$primary_image %||% NA_character_,
        most_recent_team = player$most_recent_team_name %||% NA_character_,
        most_recent_team_code = player$most_recent_team_code %||% NA_character_
      )
    }
    
    new_profiles <- map_dfr(new_player_ids$player_id, function(pid) {
      result <- fetch_player_profile(pid)
      Sys.sleep(0.2)
      result
    })
    
    if (nrow(new_profiles) > 0) {
      updated_info <- existing_players_info %>%
        align_col_types(new_profiles) %>%
        bind_rows(new_profiles)
      write_csv(updated_info, file.path(data_dir, "pwhl_players_info.csv"))
      message("  ✓ Added ", nrow(new_profiles), " player profiles")
    }
  } else {
    message("  ✓ No new players")
  }
}

# ============================
# 5) UPDATE TRANSACTIONS
# ============================

message("\n=== Updating Transactions ===")

existing_transactions <- read_csv(file.path(data_dir, "pwhl_transactions.csv"), 
                                 show_col_types = FALSE) %>%
  mutate(season_id = as.character(season_id))

fetch_transactions_for_season <- function(season_id) {
  res <- GET(base_url, query = c(common_params, list(
    view = "statviewtype", type = "transactions", season_id = season_id
  )))

  if (http_error(res)) return(NULL)

  txt <- content(res, as = "text", encoding = "UTF-8")
  js <- tryCatch(fromJSON(txt, flatten = TRUE), error = function(e) NULL)
  
  if (is.null(js)) return(NULL)
  
  trans <- js$SiteKit$Statviewtype$transactions
  if (is.null(trans) || length(trans) == 0) return(NULL)

  df <- tryCatch(as_tibble(trans), error = function(e) NULL)
  if (is.null(df) || nrow(df) == 0) return(NULL)

  df %>% mutate(season_id = as.character(season_id))
}

# Fetch current transactions
current_transactions <- map_dfr(all_seasons$season_id, function(sid) {
  result <- fetch_transactions_for_season(sid)
  Sys.sleep(0.3)
  result
})

# Compare and update if new transactions exist
if (nrow(current_transactions) > nrow(existing_transactions)) {
  write_csv(current_transactions, file.path(data_dir, "pwhl_transactions.csv"))
  message("  ✓ Updated transactions (", 
          nrow(current_transactions) - nrow(existing_transactions), " new)")
  
  # Update team logos
  team_logos <- current_transactions %>%
    filter(!is.na(team_logo)) %>%
    select(season_id, team_id, team_name, team_city, team_code, team_logo) %>%
    distinct() %>%
    arrange(season_id, team_id)
  
  write_csv(team_logos, file.path(data_dir, "pwhl_team_logos.csv"))
} else {
  message("  ✓ No new transactions")
}

# ============================
# 6) UPDATE PLAY-BY-PLAY DATA
# ============================

message("\n=== Updating Play-by-Play Data ===")

# Same reasoning as sections 3/4: compare against every final game
# (pwhl_season_game_ids.csv, rewritten fresh every run in section 1) rather
# than new_games, so a PBP gap from an earlier crashed run still gets
# caught up once game-summary detection stops finding anything "new".
all_final_games <- read_csv(file.path(data_dir, "pwhl_season_game_ids.csv"), show_col_types = FALSE) %>%
  mutate(season_id = as.character(season_id), game_id = as.character(game_id)) %>%
  filter(is_final)

existing_pbp_game_ids <- read_csv(file.path(data_dir, "pwhl_pbp.csv"), show_col_types = FALSE) %>%
  mutate(game_id = as.character(game_id)) %>%
  distinct(game_id)

games_needing_pbp <- all_final_games %>%
  anti_join(existing_pbp_game_ids, by = "game_id")

if (nrow(games_needing_pbp) > 0) {
  # Everything in this section depends on the fastRhockey package hitting an
  # external API; a failure here shouldn't take down the game/player/
  # transaction updates above, which are already written to disk by now.
  pbp_result <- tryCatch({
    # Get fastRhockey seasons to get schedule metadata
    pwhl_seasons <- pwhl_season_id()

    # Fetch schedule for new games to get season_yr and game_type
    sched_for_new <- map2_dfr(
      pwhl_seasons$season_yr,
      pwhl_seasons$game_type_label,
      function(yr, gtype) {
        out <- tryCatch(
          pwhl_schedule(season = yr, game_type = gtype),
          error = function(e) NULL
        )
        if (!is.null(out) && nrow(out) > 0) {
          out %>%
            mutate(season_yr = yr, game_type_label = gtype, game_id = as.character(game_id))
        } else {
          NULL
        }
      }
    )

    # Filter to only games missing PBP
    new_games_pbp <- sched_for_new %>%
      filter(game_id %in% games_needing_pbp$game_id)

    if (nrow(new_games_pbp) > 0) {
      new_pbp_list <- vector("list", nrow(new_games_pbp))
      fail_log <- tibble(game_id = character(), error = character())

      for (i in seq_len(nrow(new_games_pbp))) {
        gid <- new_games_pbp$game_id[i]
        message("  Fetching PBP for game ", gid)

        pbp <- tryCatch(
          fastRhockey::pwhl_pbp(game_id = gid),
          error = function(e) {
            fail_log <<- bind_rows(
              fail_log,
              tibble(game_id = as.character(gid), error = conditionMessage(e))
            )
            NULL
          }
        )

        if (!is.null(pbp) && nrow(pbp) > 0) {
          new_pbp_list[[i]] <- pbp
        }

        Sys.sleep(0.4)
      }

      # Drop NULLs
      new_pbp_list <- new_pbp_list[!vapply(new_pbp_list, is.null, logical(1))]

      if (length(new_pbp_list) > 0) {
        new_pbp <- bind_rows(new_pbp_list) %>%
          mutate(game_id = as.character(game_id))

        # Join with schedule metadata
        sched_join <- new_games_pbp %>%
          select(game_id, game_date, home_team, away_team,
                 home_score, away_score, season_yr, game_type_label)

        new_pbp <- new_pbp %>%
          left_join(sched_join, by = "game_id")

        existing_pbp <- read_csv(file.path(data_dir, "pwhl_pbp.csv"),
                                 show_col_types = FALSE) %>%
          mutate(game_id = as.character(game_id))
        updated_pbp <- existing_pbp %>%
          anti_join(new_pbp, by = "game_id") %>%
          align_col_types(new_pbp) %>%
          bind_rows(new_pbp)
        write_csv(updated_pbp, file.path(data_dir, "pwhl_pbp.csv"))
        message("  ✓ Added ", nrow(new_pbp), " play-by-play events")

        if (nrow(fail_log) > 0) {
          message("  ⚠ ", nrow(fail_log), " games failed to fetch PBP")
        }
      }
    }
    TRUE
  }, error = function(e) {
    message("  ⚠ Play-by-play update failed, skipping: ", conditionMessage(e))
    FALSE
  })
} else {
  message("  ✓ No play-by-play gaps found")
}

# ============================
# 7) UPDATE STANDINGS
# ============================

message("\n=== Updating Standings ===")

# Standings live on a different feed (statviewfeed, not modulekit) with a
# different public key, and the response is wrapped in bare parentheses
# instead of a named JSONP callback -- strip those instead of the
# callback-regex used elsewhere. Two calls per season: "league" grouping has
# the core W/L/points/GF/GA, "division" grouping has PP/PK detail; join them
# on team_id.
fetch_standings_view <- function(season_id, group_by) {
  res <- GET(
    base_url,
    query = list(
      feed          = "statviewfeed",
      view          = "teams",
      groupTeamsBy  = group_by,
      context       = "overall",
      site_id       = "2",
      season        = season_id,
      special       = if (group_by == "division") "true" else "false",
      key           = "694cfeed58c932ee",
      client_code   = client_code,
      league_id     = "1",
      division      = if (group_by == "division") "-1" else "undefined",
      sort          = "points",
      lang          = "en"
    )
  )
  if (http_error(res)) return(NULL)

  txt <- content(res, as = "text", encoding = "UTF-8")
  txt <- sub("^\\(", "", txt)
  txt <- sub("\\)$", "", txt)
  js <- tryCatch(fromJSON(txt, simplifyVector = FALSE), error = function(e) NULL)
  if (is.null(js) || length(js) == 0) return(NULL)

  data_list <- js[[1]]$sections[[1]]$data
  if (is.null(data_list) || length(data_list) == 0) return(NULL)

  rows <- map(data_list, function(x) {
    row <- x$row
    row$team_id   <- scalar_chr(x$prop$team_code$teamLink %||% x$prop$name$teamLink)
    row$team_code <- sub("^[a-z]+ - ", "", scalar_chr(row$team_code))
    row$name      <- sub("^[a-z]+ - ", "", scalar_chr(row$name))
    as_tibble(row)
  })
  bind_rows(rows)
}

fetch_standings_for_season <- function(season_id) {
  league_df   <- fetch_standings_view(season_id, "league")
  Sys.sleep(0.2)
  division_df <- fetch_standings_view(season_id, "division")
  if (is.null(league_df) && is.null(division_df)) return(NULL)

  if (!is.null(division_df)) {
    division_df <- division_df %>% select(-any_of(c("name", "rank")))
  }

  combined <- if (!is.null(league_df) && !is.null(division_df)) {
    league_df %>% left_join(division_df, by = c("team_id", "team_code"))
  } else {
    league_df %||% division_df
  }

  combined %>% mutate(season_id = as.character(season_id))
}

# Always a full refresh, not an upsert -- standings are a current snapshot,
# not an append-only log, and the dataset is small enough (a handful of
# rows per season) that there's no benefit to tracking a diff.
all_standings <- map_dfr(all_seasons$season_id, function(sid) {
  result <- fetch_standings_for_season(sid)
  Sys.sleep(0.3)
  result
})

if (nrow(all_standings) > 0) {
  write_csv(all_standings, file.path(data_dir, "pwhl_standings.csv"))
  message("  ✓ Updated standings for ", length(unique(all_standings$season_id)), " season(s)")
} else {
  message("  ⚠ No standings data returned")
}

# ============================
# 8) UPDATE TEAM ROSTERS
# ============================

message("\n=== Updating Team Rosters ===")

fetch_team_roster <- function(team_id, season_id) {
  res <- GET(base_url, query = c(common_params, list(view = "roster", team_id = team_id, season_id = season_id)))
  if (http_error(res)) return(NULL)

  # Unlike the other feeds this script parses, each roster entry has a
  # `draftinfo` field that's an empty array (`[]`) rather than a scalar --
  # that breaks jsonlite's auto-simplification into a data.frame (it comes
  # back as a plain nested list instead), so flatten=TRUE + as_tibble()
  # silently produced zero rows for every team. Parse fully unsimplified
  # and flatten each player to scalars by hand instead.
  txt <- content(res, as = "text", encoding = "UTF-8")
  js <- tryCatch(fromJSON(txt, simplifyVector = FALSE), error = function(e) NULL)
  roster <- js$SiteKit$Roster
  if (is.null(roster) || length(roster) == 0) return(NULL)

  df <- tryCatch(
    bind_rows(map(roster, function(p) as_tibble(lapply(p, scalar_chr)))),
    error = function(e) NULL
  )
  if (is.null(df) || nrow(df) == 0) return(NULL)

  df %>%
    mutate(
      team_id   = as.character(team_id),
      season_id = as.character(season_id),
      player_id = as.character(player_id)
    )
}

# Current roster is a snapshot (like standings), not an append-only log --
# full refresh every run, keyed off the team/season pairs already known
# from pwhl_teams.csv.
team_season_pairs <- read_csv(file.path(data_dir, "pwhl_teams.csv"), show_col_types = FALSE) %>%
  mutate(team_id = as.character(team_id), season_id = as.character(season_id)) %>%
  distinct(season_id, team_id)

all_rosters <- map2_dfr(team_season_pairs$season_id, team_season_pairs$team_id, function(sid, tid) {
  result <- fetch_team_roster(tid, sid)
  Sys.sleep(0.2)
  result
})

if (nrow(all_rosters) > 0) {
  write_csv(all_rosters, file.path(data_dir, "pwhl_team_rosters.csv"))
  message("  ✓ Updated rosters for ", nrow(team_season_pairs), " team-season(s)")
} else {
  message("  ⚠ No roster data returned")
}

# ============================
# 9) UPDATE PLAYER SEASON STATS
# ============================

message("\n=== Updating Player Season Stats ===")

fetch_player_season_stats <- function(player_id) {
  res <- GET(base_url, query = c(common_params, list(view = "player", category = "seasonstats", player_id = player_id)))
  if (http_error(res)) return(NULL)

  txt <- content(res, as = "text", encoding = "UTF-8")
  js <- tryCatch(fromJSON(txt, flatten = TRUE), error = function(e) NULL)
  player_data <- js$SiteKit$Player
  if (is.null(player_data)) return(NULL)

  rows <- list()
  for (stat_type in c("regular", "playoff", "exhibition")) {
    block <- player_data[[stat_type]]
    if (is.null(block) || length(block) == 0) next
    df <- tryCatch(as_tibble(block), error = function(e) NULL)
    if (is.null(df) || nrow(df) == 0) next
    rows[[stat_type]] <- df %>% mutate(stat_type = stat_type)
  }
  if (length(rows) == 0) return(NULL)

  bind_rows(rows) %>%
    mutate(player_id = as.character(player_id), season_id = as.character(season_id))
}

# Self-healing like sections 3/4/6: refresh anyone whose game log just
# changed this run, plus backfill anyone who has never been fetched at all
# (covers both new players and this feature's own bootstrap on first run).
existing_season_stats_ids <- tryCatch(
  read_csv(file.path(data_dir, "pwhl_player_season_stats.csv"), show_col_types = FALSE) %>%
    mutate(player_id = as.character(player_id)) %>%
    distinct(player_id),
  error = function(e) tibble(player_id = character())
)

players_needing_season_stats <- bind_rows(
  new_player_list %>% select(player_id),
  all_game_players %>% distinct(player_id) %>% anti_join(existing_season_stats_ids, by = "player_id")
) %>%
  distinct(player_id) %>%
  filter(!is.na(player_id))

if (nrow(players_needing_season_stats) > 0) {
  updated_season_stats <- map_dfr(players_needing_season_stats$player_id, function(pid) {
    result <- fetch_player_season_stats(pid)
    Sys.sleep(0.2)
    result
  })

  if (nrow(updated_season_stats) > 0) {
    existing_season_stats <- tryCatch(
      read_csv(file.path(data_dir, "pwhl_player_season_stats.csv"), show_col_types = FALSE) %>%
        mutate(player_id = as.character(player_id)),
      error = function(e) tibble()
    )
    final_season_stats <- if (nrow(existing_season_stats) > 0) {
      existing_season_stats %>%
        anti_join(players_needing_season_stats, by = "player_id") %>%
        align_col_types(updated_season_stats) %>%
        bind_rows(updated_season_stats)
    } else {
      updated_season_stats
    }
    write_csv(final_season_stats, file.path(data_dir, "pwhl_player_season_stats.csv"))
    message("  ✓ Updated season stats for ", nrow(players_needing_season_stats), " player(s)")
  }
} else {
  message("  ✓ No player season stats missing")
}

# ============================
# 10) UPDATE PLAYOFF BRACKET
# ============================

message("\n=== Updating Playoff Bracket ===")

fetch_bracket_for_season <- function(season_id) {
  res <- GET(base_url, query = c(common_params, list(view = "brackets", season_id = season_id)))
  if (http_error(res)) return(NULL)

  txt <- content(res, as = "text", encoding = "UTF-8")
  js <- tryCatch(fromJSON(txt, simplifyVector = FALSE), error = function(e) NULL)
  brackets <- js$SiteKit$Brackets
  if (is.null(brackets) || is.null(brackets$rounds) || length(brackets$rounds) == 0) return(NULL)

  teams_map <- brackets$teams %||% list()
  team_name <- function(tid) {
    tid_chr <- scalar_chr(tid)
    if (is.na(tid_chr)) return(NA_character_)
    t <- teams_map[[tid_chr]]
    if (is.null(t)) NA_character_ else scalar_chr(t$name)
  }

  # A JSON collection with exactly one item sometimes arrives as a bare
  # object instead of a 1-element array (e.g. a playoff round with a single
  # matchup) -- a plain `for` loop over that object would then iterate over
  # its individual FIELDS instead of over "the one item", and blow up with
  # "$ operator is invalid for atomic vectors" the moment a leaf value (like
  # a round number "1") gets treated as an item. Detect a bare single object
  # (named list) and wrap it before iterating.
  as_item_list <- function(x) {
    if (is.null(x) || length(x) == 0) return(list())
    nm <- names(x)
    if (!is.null(nm) && any(nzchar(nm))) list(x) else x
  }

  rows <- list()
  for (round in as_item_list(brackets$rounds)) {
    for (matchup in as_item_list(round$matchups)) {
      for (g in as_item_list(matchup$games)) {
        rows[[length(rows) + 1]] <- tibble(
          season_id         = as.character(season_id),
          round             = scalar_chr(round$round),
          round_name        = scalar_chr(round$round_name),
          series_letter     = scalar_chr(matchup$series_letter),
          team1_id          = scalar_chr(matchup$team1),
          team1_name        = team_name(matchup$team1),
          team2_id          = scalar_chr(matchup$team2),
          team2_name        = team_name(matchup$team2),
          team1_series_wins = suppressWarnings(as.integer(matchup$team1_wins)),
          team2_series_wins = suppressWarnings(as.integer(matchup$team2_wins)),
          game_id           = scalar_chr(g$game_id),
          home_team_id      = scalar_chr(g$home_team),
          home_goals        = suppressWarnings(as.integer(g$home_goal_count)),
          visiting_team_id  = scalar_chr(g$visiting_team),
          visiting_goals    = suppressWarnings(as.integer(g$visiting_goal_count)),
          game_status       = scalar_chr(g$game_status),
          game_date         = scalar_chr(g$date_time)
        )
      }
    }
  }
  if (length(rows) == 0) return(NULL)
  bind_rows(rows)
}

# Full refresh every run, same reasoning as standings/rosters -- cheap
# (most seasons return nothing, since most seasons have no playoffs yet).
all_brackets <- map_dfr(all_seasons$season_id, function(sid) {
  result <- fetch_bracket_for_season(sid)
  Sys.sleep(0.3)
  result
})

if (nrow(all_brackets) > 0) {
  write_csv(all_brackets, file.path(data_dir, "pwhl_playoff_bracket.csv"))
  message("  ✓ Updated playoff bracket (", length(unique(all_brackets$season_id)), " season(s) with playoff data)")
} else {
  message("  ✓ No playoff bracket data found")
}

# ============================
# 11) UPDATE PLAYER MEDIA
# ============================

message("\n=== Updating Player Media ===")

fetch_player_media <- function(player_id) {
  res <- GET(base_url, query = c(common_params, list(view = "player", category = "media", player_id = player_id)))
  if (http_error(res)) return(NULL)

  txt <- content(res, as = "text", encoding = "UTF-8")
  js <- tryCatch(fromJSON(txt, flatten = TRUE), error = function(e) NULL)
  media <- js$SiteKit$Player
  if (is.null(media) || length(media) == 0) return(NULL)

  df <- tryCatch(as_tibble(media), error = function(e) NULL)
  if (is.null(df) || nrow(df) == 0) return(NULL)

  df %>%
    mutate(player_id = as.character(player_id)) %>%
    rename(media_id = id) %>%
    select(any_of(c("player_id", "media_id", "media_type", "is_primary", "url", "thumb", "title", "width", "height", "uploaded")))
}

# This file was an orphaned one-time bootstrap snapshot (initial_setup.R,
# which fetched it, was never committed) -- self-heal by fetching anyone
# who has never had a media row captured at all.
existing_media_ids <- tryCatch(
  read_csv(file.path(data_dir, "pwhl_players_media.csv"), show_col_types = FALSE) %>%
    mutate(player_id = as.character(player_id)) %>%
    distinct(player_id),
  error = function(e) tibble(player_id = character())
)

players_needing_media <- all_game_players %>%
  distinct(player_id) %>%
  filter(!is.na(player_id)) %>%
  anti_join(existing_media_ids, by = "player_id")

if (nrow(players_needing_media) > 0) {
  updated_media <- map_dfr(players_needing_media$player_id, function(pid) {
    result <- fetch_player_media(pid)
    Sys.sleep(0.2)
    result
  })

  if (nrow(updated_media) > 0) {
    existing_media <- tryCatch(
      read_csv(file.path(data_dir, "pwhl_players_media.csv"), show_col_types = FALSE) %>%
        mutate(player_id = as.character(player_id)),
      error = function(e) tibble()
    )
    final_media <- if (nrow(existing_media) > 0) {
      existing_media %>%
        anti_join(players_needing_media, by = "player_id") %>%
        align_col_types(updated_media) %>%
        bind_rows(updated_media)
    } else {
      updated_media
    }
    write_csv(final_media, file.path(data_dir, "pwhl_players_media.csv"))
    message("  ✓ Updated media for ", nrow(players_needing_media), " player(s)")
  }
} else {
  message("  ✓ No player media missing")
}

# ============================
# DONE
# ============================

message("\n", rep("=", 50))
message("✅ Daily update complete!")
message(rep("=", 50))
message("\nTimestamp: ", Sys.time())
if (nrow(new_games) > 0) {
  message("Updated files with ", nrow(new_games), " new game(s)")
} else {
  message("No updates needed - all data is current")
}
message(rep("=", 50))
