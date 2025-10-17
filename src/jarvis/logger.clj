(ns jarvis.logger
  (:require [cheshire.core :as json]
            [clojure.java.io :as io])
  (:import [java.time.format DateTimeFormatter]
           [java.time ZonedDateTime ZoneId]))

(def ^:private log-file-path
  "/home/paul/Work/jarvis/ai-detector/conversation.jsonl")

(defn ensure-log-directory []
  "Ensure the log directory exists"
  (let [file (io/file log-file-path)
        parent (.getParentFile file)]
    (when parent
      (.mkdirs parent))))

(defn get-timestamp []
  "Get current timestamp in ISO 8601 format"
  (.format (ZonedDateTime/now (ZoneId/systemDefault))
           DateTimeFormatter/ISO_OFFSET_DATE_TIME))

(defn parse-timestamp [timestamp-str]
  "Parse ISO 8601 timestamp to milliseconds since epoch"
  (try
    (let [instant (.toInstant (ZonedDateTime/parse timestamp-str DateTimeFormatter/ISO_OFFSET_DATE_TIME))]
      (.toEpochMilli instant))
    (catch Exception e
      0)))

(defn filter-recent-entries
  "Keep only entries from the last 5 minutes"
  [entries]
  (let [five-minutes-ms (* 5 60 1000)
        now-ms (System/currentTimeMillis)
        cutoff-ms (- now-ms five-minutes-ms)]
    (filter
      (fn [entry]
        (let [entry-ms (parse-timestamp (:timestamp entry))]
          (> entry-ms cutoff-ms)))
      entries)))

(defn read-log-entries []
  "Read all entries from the log file"
  (try
    (let [file (io/file log-file-path)]
      (if (.exists file)
        (with-open [reader (io/reader log-file-path)]
          (doall
            (for [line (line-seq reader)
                  :when (not (clojure.string/blank? line))]
              (json/parse-string line true))))
        []))
    (catch Exception e
      (println "[ERROR] Failed to read log entries:" (.getMessage e))
      [])))

(defn write-log-entries [entries]
  "Write entries to the log file (overwrite)"
  (try
    (ensure-log-directory)
    (with-open [writer (io/writer log-file-path)]
      (doseq [entry entries]
        (.write writer (json/generate-string entry))
        (.write writer "\n")))
    true
    (catch Exception e
      (println "[ERROR] Failed to write log entries:" (.getMessage e))
      false)))

(defn log-conversation
  "Log a conversation message to the JSONL file, keeping only last 5 minutes"
  ([message]
   (log-conversation message "jarvis"))
  ([message user]
   (try
     (ensure-log-directory)
     (let [entry {:message message
                  :user user
                  :timestamp (get-timestamp)}
           ;; Read existing entries
           existing-entries (read-log-entries)
           ;; Add new entry
           all-entries (conj existing-entries entry)
           ;; Filter to last 5 minutes
           recent-entries (filter-recent-entries all-entries)]
       ;; Write back filtered entries
       (write-log-entries recent-entries))
     (catch Exception e
       (println "[ERROR] Failed to log conversation:" (.getMessage e))
       false))))
