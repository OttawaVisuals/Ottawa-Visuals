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

`%||%` <- function(x, y) if (!is.null(x)) x else y

scalar_chr <- function(x) {
  if (is.null(x) || length(x) == 0) return(NA_character_)
  if (is.data.frame(x)) x <- x[[1]]
  if (length(x) == 0) return(NA_character_)
  as.character(x[1])
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
    shootout_rounds     = suppressWarnings(as.integer(meta$shootout_rounds %||% meta$shootout %||% NA))
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

# Load existing game IDs and ensure consistent types
existing_games <- read_csv(file.path(data_dir, "pwhl_season_game_ids.csv"), 
                          show_col_types = FALSE) %>%
  mutate(
    season_id = as.character(season_id),
    game_id = as.character(game_id)
  )

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

current_games <- all_games %>%
  select(season_id, game_id) %>%
  mutate(game_id = as.character(game_id))

# Find new games
new_games <- current_games %>%
  anti_join(existing_games, by = c("season_id", "game_id"))

if (nrow(new_games) == 0) {
  message("  ✓ No new games found")
} else {
  message("  ✓ Found ", nrow(new_games), " new game(s)")
  
  # Update game IDs file
  write_csv(current_games, file.path(data_dir, "pwhl_season_game_ids.csv"))
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
                                   show_col_types = FALSE) %>%
      mutate(game_id = as.character(game_id), season_id = as.character(season_id))
    updated_summaries <- bind_rows(existing_summaries, new_game_summaries)
    write_csv(updated_summaries, file.path(data_dir, "pwhl_game_summaries.csv"))
    message("  ✓ Added ", nrow(new_game_summaries), " game summaries")
  }
  
  if (nrow(new_game_players) > 0) {
    existing_players <- read_csv(file.path(data_dir, "pwhl_game_players.csv"), 
                                 show_col_types = FALSE) %>%
      mutate(game_id = as.character(game_id), season_id = as.character(season_id))
    updated_players <- bind_rows(existing_players, new_game_players)
    write_csv(updated_players, file.path(data_dir, "pwhl_game_players.csv"))
    message("  ✓ Added ", nrow(new_game_players), " game player records")
  }
}

# ============================
# 3) UPDATE PLAYER GAME LOGS
# ============================

if (nrow(new_games) > 0) {
  message("\n=== Updating Player Game Logs ===")
  
  # Get unique player/season combinations from new games
  new_player_list <- new_game_players %>%
    filter(!is.na(player_id)) %>%
    mutate(player_id = as.character(player_id), season_id = as.character(season_id)) %>%
    distinct(season_id, player_id)
  
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

    df %>% mutate(season_id = as.character(season_id), player_id = as.character(player_id), game_id = as.character(id))
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
               player_id = as.character(player_id))
      
      # Remove old entries for updated players, then add new data
      final_logs <- existing_logs %>%
        anti_join(new_player_list, by = c("season_id", "player_id")) %>%
        bind_rows(updated_logs)
      
      write_csv(final_logs, file.path(data_dir, "pwhl_player_game_logs.csv"))
      message("  ✓ Updated logs for ", nrow(new_player_list), " players")
    }
  }
}

# ============================
# 4) UPDATE PLAYER INFO (for new players only)
# ============================

message("\n=== Checking for New Players ===")

existing_players_info <- read_csv(file.path(data_dir, "pwhl_players_info.csv"), 
                                 show_col_types = FALSE) %>%
  mutate(player_id = as.character(player_id))

if (nrow(new_games) > 0 && nrow(new_game_players) > 0) {
  new_player_ids <- new_game_players %>%
    filter(!is.na(player_id)) %>%
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
      updated_info <- bind_rows(existing_players_info, new_profiles)
      write_csv(updated_info, file.path(data_dir, "pwhl_players_info.csv"))
      message("  ✓ Added ", nrow(new_profiles), " player profiles")
    }
  } else {
    message("  ✓ No new players")
  }
} else {
  message("  ✓ No new players")
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

if (nrow(new_games) > 0) {
  message("\n=== Updating Play-by-Play Data ===")
  
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
  
  # Filter to only new games
  new_games_pbp <- sched_for_new %>%
    filter(game_id %in% new_games$game_id)
  
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
      updated_pbp <- bind_rows(existing_pbp, new_pbp)
      write_csv(updated_pbp, file.path(data_dir, "pwhl_pbp.csv"))
      message("  ✓ Added ", nrow(new_pbp), " play-by-play events")
      
      if (nrow(fail_log) > 0) {
        message("  ⚠ ", nrow(fail_log), " games failed to fetch PBP")
      }
    }
  }
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
