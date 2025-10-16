(ns jarvis.core
  (:require [jarvis.audio :as audio]
           [jarvis.whisper :as whisper]
           [jarvis.typer :as typer])
  (:gen-class))

(def ^:private shutdown-signal (atom false))
(def ^:private trigger-file "/tmp/jarvis-type-trigger")
(def ^:private last-trigger-time (atom 0))

(defn get-temp-audio-file []
  "Generate a temporary audio file path"
  (str (System/getProperty "java.io.tmpdir") "/whisper_" (System/currentTimeMillis) ".wav"))

(defn check-trigger-file []
  "Check if trigger file has been modified since last check"
  (try
    (let [file (java.io.File. trigger-file)]
      (when (.exists file)
        (let [last-modified (.lastModified file)]
          (when (> last-modified @last-trigger-time)
            (reset! last-trigger-time last-modified)
            true))))
    (catch Exception e
      false)))

(defn record-and-type []
  "Record audio and type the transcribed text"
  (println "\n[TYPING MODE] Recording... speak now")
  (flush)

  (let [audio-file (get-temp-audio-file)
        duration-ms 5000]

    ;; Record audio
    (if (audio/record-audio-to-file audio-file duration-ms)
      (let [file-size (.length (java.io.File. audio-file))]
        ;; Check if audio is not silent
        (if (> file-size 20000)
          (let [result (whisper/transcribe-audio audio-file)]
            (if (:success result)
              (let [text (:text result)]
                (when (and text (> (.length text) 0))
                  (println "\n" (apply str (repeat 60 "=")))
                  (println "[WILL TYPE]")
                  (println text)
                  (println (apply str (repeat 60 "=")))
                  (println "\n>>> CLICK WHERE YOU WANT TO TYPE NOW! <<<")
                  (println "Typing in 3 seconds...")
                  (flush)
                  ;; Countdown
                  (Thread/sleep 1000)
                  (println "2...")
                  (flush)
                  (Thread/sleep 1000)
                  (println "1...")
                  (flush)
                  (Thread/sleep 1000)
                  ;; Type the text
                  (println "[TYPING NOW]")
                  (flush)
                  (typer/type-text text)
                  (println "[OK] Typed successfully")
                  (flush)))
              (println "[ERROR] Transcription failed:" (:error result))))
          (println "[SILENT] No speech detected")))
      (println "[ERROR] Failed to record audio")))

  (flush))

(defn continuous-logging []
  "Continuously record and log audio, and watch for trigger file"
  (println "\n[LISTENING] Continuous speech-to-text logging started")
  (println "[INFO] Speaking now - everything will be logged to console")
  (println "[INFO] To type mode: touch" trigger-file "\n")
  (flush)

  (loop []
    (if @shutdown-signal
      (println "\n[STOP] Logging stopped")
      (do
        ;; Check for trigger file
        (when (check-trigger-file)
          (println "\n[TRIGGER DETECTED] Switching to typing mode...")
          (flush)
          (record-and-type))

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
