(ns jarvis.audio
  (:require [clojure.core.async :as async])
  (:import [javax.sound.sampled AudioFormat AudioSystem TargetDataLine SourceDataLine]
           [java.io File]
           [javax.sound.sampled AudioFileFormat$Type]))

(def ^:private recording (atom false))
(def ^:private recorder-thread (atom nil))

(def SAMPLE_RATE 16000.0)
(def BITS_PER_SAMPLE 16)
(def CHANNELS 1)

(defn get-audio-format []
  "Create audio format for recording"
  (AudioFormat. SAMPLE_RATE BITS_PER_SAMPLE CHANNELS true false))

(defn get-target-line [audio-format]
  "Get the microphone input line"
  (let [line-info (javax.sound.sampled.DataLine$Info.
                    TargetDataLine
                    audio-format)]
    (AudioSystem/getLine line-info)))

(defn record-audio-to-file [output-file duration-ms]
  "Record audio for specified duration (in ms) and save to file"
  (try
    (let [audio-format (get-audio-format)
          target-line (get-target-line audio-format)
          buffer (byte-array (* SAMPLE_RATE (/ BITS_PER_SAMPLE 8) (/ duration-ms 1000)))
          bytes-per-ms (* SAMPLE_RATE (/ BITS_PER_SAMPLE 8) 0.001)]

      ;; Open and start recording
      (.open target-line)
      (.start target-line)

      ;; Record data in chunks
      (let [chunk-size (int (* bytes-per-ms 100)) ;; 100ms chunks
            start-time (System/currentTimeMillis)]
        (loop [offset 0]
          (let [elapsed (- (System/currentTimeMillis) start-time)
                bytes-read (.read target-line buffer offset (min chunk-size (- (alength buffer) offset)))]
            (if (and (< elapsed duration-ms) (< offset (alength buffer)))
              (recur (+ offset bytes-read))
              (do
                (.stop target-line)
                (.close target-line)
                ;; Write WAV file
                (let [audio-input-stream (javax.sound.sampled.AudioInputStream.
                                           (java.io.ByteArrayInputStream. buffer 0 (+ offset bytes-read))
                                           audio-format
                                           (long (/ (+ offset bytes-read)
                                                   (/ BITS_PER_SAMPLE 8))))]
                  (javax.sound.sampled.AudioSystem/write
                    audio-input-stream
                    AudioFileFormat$Type/WAVE
                    (File. output-file)))
                true)))))
      )
    (catch Exception e
      (println "Error recording audio:" (.getMessage e))
      false)))

(defn record-until-condition [output-file condition-fn check-interval-ms]
  "Record audio until a condition is met (e.g., Ctrl key released)"
  (try
    (let [audio-format (get-audio-format)
          target-line (get-target-line audio-format)
          chunk-size (int (* SAMPLE_RATE (/ BITS_PER_SAMPLE 8) 0.05)) ;; 50ms chunks
          buffer (java.io.ByteArrayOutputStream.)]

      ;; Open and start recording
      (.open target-line)
      (.start target-line)

      ;; Record until condition is met
      (let [temp-buffer (byte-array chunk-size)]
        (loop []
          (let [bytes-read (.read target-line temp-buffer 0 chunk-size)]
            (when (> bytes-read 0)
              (.write buffer temp-buffer 0 bytes-read))
            (if (condition-fn)
              (do
                (.stop target-line)
                (.close target-line)
                ;; Write WAV file
                (let [audio-data (.toByteArray buffer)
                      audio-input-stream (javax.sound.sampled.AudioInputStream.
                                           (java.io.ByteArrayInputStream. audio-data)
                                           audio-format
                                           (long (/ (alength audio-data)
                                                   (/ BITS_PER_SAMPLE 8))))]
                  (javax.sound.sampled.AudioSystem/write
                    audio-input-stream
                    AudioFileFormat$Type/WAVE
                    (File. output-file)))
                true)
              (do
                (Thread/sleep check-interval-ms)
                (recur))))))
      )
    (catch Exception e
      (println "Error in record-until-condition:" (.getMessage e))
      false)))
