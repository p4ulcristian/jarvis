(ns jarvis.core
  (:require [jarvis.audio :as audio]
           [jarvis.nemo :as nemo]
           [jarvis.typer :as typer]
           [jarvis.logger :as logger]
           [clojure.java.io :as io])
  (:gen-class))

(def ^:private shutdown-signal (atom false))
(def ^:private trigger-file "/tmp/jarvis-type-trigger")
(def ^:private last-trigger-time (atom 0))

;; Rolling buffer for AI detection (stores last 5 minutes)
(def ^:private transcription-buffer (atom []))
(def ^:private five-minutes-ms (* 5 60 1000))

;; AI detection state
(def ^:private last-detection-time (atom 0))
(def ^:private detection-cooldown-ms (* 30 1000)) ;; 30 seconds cooldown

;; Keyboard listener state
(def ^:private keyboard-listener-process (atom nil))
(def ^:private keyboard-event-file "/tmp/jarvis-keyboard-events")
(def ^:private keyboard-state-file "/tmp/jarvis-ctrl-state")
(def ^:private last-event-position (atom 0))

(defn get-temp-audio-file []
  "Generate a temporary audio file path"
  (str (System/getProperty "java.io.tmpdir") "/nemo_" (System/currentTimeMillis) ".wav"))

;; ============================================================================
;; Rolling Buffer Management
;; ============================================================================

(defn add-to-buffer [text]
  "Add a transcription to the buffer with current timestamp"
  (let [entry {:text text
               :timestamp (System/currentTimeMillis)}]
    (swap! transcription-buffer conj entry)))

(defn clean-buffer []
  "Remove entries older than 5 minutes from the buffer"
  (let [now (System/currentTimeMillis)
        cutoff (- now five-minutes-ms)]
    (swap! transcription-buffer
           (fn [buffer]
             (filterv #(> (:timestamp %) cutoff) buffer)))))

(defn get-buffer-text []
  "Get all text from the buffer as a single string"
  (clean-buffer)
  (clojure.string/join " " (map :text @transcription-buffer)))

;; ============================================================================
;; AI Detection
;; ============================================================================

(defn check-ai-detection []
  "Check if the buffer text is directed at the AI (with cooldown)"
  (try
    ;; Check cooldown
    (let [now (System/currentTimeMillis)
          time-since-last-detection (- now @last-detection-time)]
      (if (< time-since-last-detection detection-cooldown-ms)
        ;; Still in cooldown, skip detection
        false
        ;; Cooldown expired, check for detection
        (let [buffer-text (get-buffer-text)]
          ;; Only check if we have some text
          (when (> (.length buffer-text) 0)
            (let [python-path (.getAbsolutePath (java.io.File. "ai-detector/venv/bin/python"))
                  script-path (.getAbsolutePath (java.io.File. "ai-detector/ai_detector_cli.py"))
                  process (.exec (Runtime/getRuntime)
                               (into-array String [python-path script-path buffer-text]))
                  exit-code (.waitFor process)]
              ;; Exit code 0 means YES (detected), 1 means NO
              (when (= exit-code 0)
                ;; Detection occurred, update last detection time
                (reset! last-detection-time now)
                true))))))
    (catch Exception e
      (println "[ERROR] AI detection failed:" (.getMessage e))
      false)))

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

;; ============================================================================
;; Keyboard Listener (Python-based)
;; ============================================================================

(defn start-keyboard-listener [script-path]
  "Start the Python keyboard listener process"
  (try
    (let [pb (ProcessBuilder. ["python3" script-path])
          process (.start pb)]
      (reset! keyboard-listener-process process)
      (reset! last-event-position 0)
      ;; Wait a moment for the listener to initialize
      (Thread/sleep 500)
      (.isAlive process))
    (catch Exception e
      (println "[ERROR] Failed to start keyboard listener:" (.getMessage e))
      false)))

(defn stop-keyboard-listener []
  "Stop the keyboard listener process"
  (when-let [process @keyboard-listener-process]
    (try
      (.destroy process)
      (.waitFor process 2 java.util.concurrent.TimeUnit/SECONDS)
      (reset! keyboard-listener-process nil)
      true
      (catch Exception e
        (println "[ERROR] Failed to stop keyboard listener:" (.getMessage e))
        false))))

(defn is-control-pressed? []
  "Check if Ctrl key is currently pressed by reading state file"
  (try
    (let [file (java.io.File. keyboard-state-file)]
      (when (.exists file)
        (let [state (slurp keyboard-state-file)]
          (= "1" (clojure.string/trim state)))))
    (catch Exception e
      false)))

(defn read-keyboard-events []
  "Read new keyboard events from the event file"
  (try
    (let [file (java.io.File. keyboard-event-file)]
      (when (.exists file)
        (let [all-content (slurp keyboard-event-file)
              new-content (subs all-content @last-event-position)
              lines (clojure.string/split-lines new-content)]
          (reset! last-event-position (count all-content))
          ;; Parse events
          (for [line lines
                :when (not (clojure.string/blank? line))
                :let [[event-type timestamp-str] (clojure.string/split line #":")]]
            {:event (keyword event-type)
             :timestamp (Long/parseLong timestamp-str)}))))
    (catch Exception e
      [])))

(defn handle-keyboard-events []
  "Handle keyboard events - just log them for testing"
  (let [events (read-keyboard-events)]
    (doseq [event events]
      (case (:event event)
        :ctrl-pressed
        (do
          (println "\n[TEST] ✓ CTRL PRESSED detected at" (:timestamp event))
          (flush))

        :ctrl-released
        (do
          (println "[TEST] ✗ CTRL RELEASED detected at" (:timestamp event))
          (flush))

        :ctrl-alone
        (do
          (println "[TEST] ⚡ CTRL pressed and released ALONE at" (:timestamp event))
          (flush))

        ;; Unknown event
        (do
          (println "[TEST] Unknown event:" event)
          (flush))))))

(defn push-to-talk-record-and-type []
  "Record audio while Ctrl is held and type when released"
  (println "\n[PUSH-TO-TALK] Recording... (release Ctrl to stop)")
  (flush)

  (let [audio-file (get-temp-audio-file)
        ;; Condition: stop recording when Ctrl is released
        stop-condition #(not (is-control-pressed?))
        check-interval-ms 50]

    ;; Record audio until Ctrl is released
    (if (audio/record-until-condition audio-file stop-condition check-interval-ms)
      (let [file-size (.length (java.io.File. audio-file))]
        ;; Check if audio is not silent
        (if (> file-size 20000)
          (let [result (nemo/transcribe-audio audio-file)]
            (if (:success result)
              (let [text (:text result)]
                (when (and text (> (.length text) 0))
                  ;; Log the transcription
                  (logger/log-conversation text "user")
                  (println "\n" (apply str (repeat 60 "=")))
                  (println "[TYPING]")
                  (println text)
                  (println (apply str (repeat 60 "=")))
                  (flush)
                  ;; Type immediately without countdown
                  (typer/type-text text)
                  (println "[OK] Typed successfully")
                  (flush)))
              (println "[ERROR] Transcription failed:" (:error result))))
          (println "[SILENT] No speech detected (recording too short)")))
      (println "[ERROR] Failed to record audio")))

  (flush))

(defn record-and-type []
  "Record audio and type the transcribed text"
  (println "\n[TYPING MODE] Recording... speak now")
  (flush)

  (let [audio-file (get-temp-audio-file)
        duration-ms 2000]

    ;; Record audio
    (if (audio/record-audio-to-file audio-file duration-ms)
      (let [file-size (.length (java.io.File. audio-file))]
        ;; Check if audio is not silent
        (if (> file-size 20000)
          (let [result (nemo/transcribe-audio audio-file)]
            (if (:success result)
              (let [text (:text result)]
                (when (and text (> (.length text) 0))
                  ;; Log the transcription
                  (logger/log-conversation text "user")
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
  (println "[INFO] To type mode: touch" trigger-file)
  (println "[INFO] Push-to-talk: Hold Ctrl key while speaking\n")
  (flush)

  (loop []
    (if @shutdown-signal
      (println "\n[STOP] Logging stopped")
      (do
        ;; Check for keyboard events
        (handle-keyboard-events)

        ;; Check for trigger file
        (when (check-trigger-file)
          (println "\n[TRIGGER DETECTED] Switching to typing mode...")
          (flush)
          (record-and-type))

        ;; Record audio for 2 seconds
        (let [audio-file (get-temp-audio-file)
              duration-ms 2000
              start-time (System/currentTimeMillis)]

          ;; Record
          (if (audio/record-audio-to-file audio-file duration-ms)
            (let [file-size (.length (java.io.File. audio-file))
                  record-end-time (System/currentTimeMillis)]
              ;; Check if audio is not silent before transcribing
              (if (> file-size 20000)
                ;; Audio file is large enough
                (let [transcribe-start-time (System/currentTimeMillis)
                      result (nemo/transcribe-audio audio-file)
                      transcribe-end-time (System/currentTimeMillis)]
                  (if (:success result)
                    (let [text (:text result)
                          total-time (- transcribe-end-time start-time)
                          recording-time (- record-end-time start-time)
                          transcription-time (- transcribe-end-time transcribe-start-time)]
                      (when (and text (> (.length text) 0))
                        ;; Add to buffer for AI detection
                        (add-to-buffer text)

                        ;; Log the transcription
                        (logger/log-conversation text "user")
                        (println "\n" (apply str (repeat 60 "=")))
                        (println "[" (.toString (java.time.LocalTime/now)) "]")
                        (println (format "[TIMING] Total: %dms | Recording: %dms | Transcription: %dms"
                                       total-time recording-time transcription-time))
                        (println text)

                        ;; Check for AI detection
                        (when (check-ai-detection)
                          (println "\n>>> [AI DETECTED] Message addressed to AI! <<<"))

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

    ;; Check NeMo server
    (println "\n[INIT] Checking NeMo server connection...")
    (flush)
    (if (nemo/start-nemo-server)
      (do
        (println "[OK] NeMo server ready")
        (flush)

        ;; Start keyboard listener
        (println "[INIT] Starting keyboard listener...")
        (flush)
        (let [script-path (.getAbsolutePath (java.io.File. "keyboard_listener.py"))]
          (if (start-keyboard-listener script-path)
            (do
              (println "[OK] Keyboard listener ready (Ctrl for push-to-talk)")
              (flush))
            (do
              (println "[WARNING] Keyboard listener failed to start")
              (println "[INFO] Push-to-talk will not be available")
              (flush))))

        ;; Start logging
        (continuous-logging)
        true)
      (do
        (println "[ERROR] Failed to connect to NeMo server")
        (println "[INFO] Make sure Docker container is running: docker-compose up -d")
        (flush)
        false))
    (catch Exception e
      (println "[ERROR] Logger startup failed:" (.getMessage e))
      (.printStackTrace e)
      false)))

(defn stop-logger []
  "Stop the logger gracefully"
  (println "\n[SHUTDOWN] Stopping logger...")
  (flush)
  (reset! shutdown-signal true)
  (stop-keyboard-listener)
  (nemo/stop-nemo-server)
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
