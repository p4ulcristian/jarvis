(ns jarvis.core
  (:require [jarvis.audio :as audio]
           [jarvis.whisper :as whisper])
  (:gen-class))

(def ^:private shutdown-signal (atom false))

(defn get-temp-audio-file []
  "Generate a temporary audio file path"
  (str (System/getProperty "java.io.tmpdir") "/whisper_" (System/currentTimeMillis) ".wav"))

(defn continuous-logging []
  "Continuously record and log audio"
  (println "\n[LISTENING] Continuous speech-to-text logging started")
  (println "[INFO] Speaking now - everything will be logged to console\n")
  (flush)

  (loop []
    (if @shutdown-signal
      (println "\n[STOP] Logging stopped")
      (do
        ;; Record audio for 5 seconds
        (let [audio-file (get-temp-audio-file)
              duration-ms 5000]

          ;; Record
          (if (audio/record-audio-to-file audio-file duration-ms)
            (let [file-size (.length (java.io.File. audio-file))]
              ;; Check if audio is not silent before transcribing
              (if (> file-size 20000)
                ;; Audio file is large enough
                (let [result (whisper/transcribe-audio audio-file)]
                  (if (:success result)
                    (let [text (:text result)]
                      (when (and text (> (.length text) 0))
                        (println "\n" (apply str (repeat 60 "=")))
                        (println "[" (.toString (java.time.LocalTime/now)) "]")
                        (println text)
                        (println (apply str (repeat 60 "=")))
                        (flush)))
                    (println "[ERROR] Transcription failed:" (:error result))))
                ;; Audio file too small (silent)
                (println "[SILENT] No speech detected, continuing...")))
            ;; Recording failed
            (println "[ERROR] Failed to record audio")))

        ;; Continue loop
        (recur)))))

(defn start-logger []
  "Start the speech-to-text logger"
  (try
    (println "\n╔════════════════════════════════════════════════════════════╗")
    (println "║         JARVIS - Continuous Speech Logger                  ║")
    (println "╚════════════════════════════════════════════════════════════╝")
    (flush)

    ;; Start Whisper server
    (println "\n[INIT] Starting Whisper server...")
    (flush)
    (let [script-path (.getAbsolutePath (java.io.File. "whisper_server.py"))]
      (if (whisper/start-whisper-server script-path)
        (do
          (println "[OK] Whisper server ready")
          (flush)
          ;; Start logging
          (continuous-logging)
          true)
        (do
          (println "[ERROR] Failed to start Whisper server")
          (flush)
          false)))
    (catch Exception e
      (println "[ERROR] Logger startup failed:" (.getMessage e))
      (.printStackTrace e)
      false)))

(defn stop-logger []
  "Stop the logger gracefully"
  (println "\n[SHUTDOWN] Stopping logger...")
  (flush)
  (reset! shutdown-signal true)
  (whisper/stop-whisper-server)
  (println "[OK] Goodbye!")
  (flush))

(defn setup-shutdown-hook []
  "Register shutdown hook for graceful cleanup"
  (.addShutdownHook
    (Runtime/getRuntime)
    (Thread. stop-logger)))

(defn -main [& args]
  "Main entry point"
  (setup-shutdown-hook)
  (if (start-logger)
    nil
    (System/exit 1)))
