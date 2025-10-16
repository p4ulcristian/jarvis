(ns jarvis.whisper
  (:require [cheshire.core :as json])
  (:import [java.io BufferedWriter OutputStreamWriter BufferedReader InputStreamReader]))

(def ^:private whisper-process (atom nil))
(def ^:private writer (atom nil))
(def ^:private reader (atom nil))

(defn start-whisper-server [python-script-path]
  "Start the persistent Python Whisper server"
  (try
    (let [process (.start (ProcessBuilder. ["python3" python-script-path]))
          out-stream (.getInputStream process)
          in-stream (.getOutputStream process)
          br (BufferedReader. (InputStreamReader. out-stream))
          bw (BufferedWriter. (OutputStreamWriter. in-stream))]

      ;; Wait for model to load
      (println "Waiting for Whisper model to load...")
      (flush)

      ;; Read startup messages from stderr until we get ready message
      (let [err-reader (BufferedReader. (InputStreamReader. (.getErrorStream process)))]
        (loop [line (.readLine err-reader)]
          (when line
            (println "[Whisper]" line)
            (flush)
            (if (and line (not (.contains line "Ready for requests")))
              (recur (.readLine err-reader))))))

      (reset! whisper-process process)
      (reset! writer bw)
      (reset! reader br)
      (println "Whisper server started successfully")
      true)
    (catch Exception e
      (println "Error starting Whisper server:" (.getMessage e))
      false)))

(defn transcribe-audio [audio-file-path]
  "Send audio file to Whisper server for transcription. Returns {:success true :text \"...\"} or {:success false :error \"...\"}"
  (if (or (nil? @writer) (nil? @reader) (nil? @whisper-process))
    {:success false :error "Whisper server not running"}
    (try
      ;; Send file path
      (.write @writer audio-file-path)
      (.newLine @writer)
      (.flush @writer)

      ;; Read JSON response
      (let [response-line (.readLine @reader)
            result (json/parse-string response-line true)]
        result)
      (catch Exception e
        {:success false :error (str "Error communicating with Whisper: " (.getMessage e))}))))

(defn stop-whisper-server []
  "Stop the Whisper server"
  (when @whisper-process
    (try
      (.destroy @whisper-process)
      (reset! whisper-process nil)
      (reset! writer nil)
      (reset! reader nil)
      (println "Whisper server stopped")
      true
      (catch Exception e
        (println "Error stopping Whisper server:" (.getMessage e))
        false))))

(defn is-running? []
  "Check if Whisper server is running"
  (boolean @whisper-process))
