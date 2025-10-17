(ns jarvis.nemo
  (:require [clj-http.client :as http]
            [cheshire.core :as json]))

(def ^:private nemo-server-url (atom "http://localhost:8000"))

(defn set-server-url! [url]
  "Set the NeMo server URL (default: http://localhost:8000)"
  (reset! nemo-server-url url))

(defn check-health []
  "Check if NeMo server is running and healthy"
  (try
    (let [response (http/get (str @nemo-server-url "/health")
                            {:as :json
                             :throw-exceptions false
                             :socket-timeout 2000
                             :connection-timeout 2000})]
      (if (= 200 (:status response))
        (do
          (println "[NeMo] Server is healthy:" (:body response))
          true)
        (do
          (println "[NeMo] Server returned non-200 status:" (:status response))
          false)))
    (catch Exception e
      (println "[NeMo] Health check failed:" (.getMessage e))
      false)))

(defn start-nemo-server []
  "Check if NeMo server is ready (no startup needed, runs in Docker)"
  (println "Checking NeMo server availability at" @nemo-server-url)
  (if (check-health)
    (do
      (println "NeMo server is ready!")
      true)
    (do
      (println "NeMo server not available. Make sure Docker container is running:")
      (println "  docker-compose up -d")
      false)))

(defn transcribe-audio [audio-file-path]
  "Send audio file to NeMo server for transcription. Returns {:success true :text \"...\"} or {:success false :error \"...\"}"
  (try
    (println "[NeMo] Transcribing audio file:" audio-file-path)
    (let [response (http/post (str @nemo-server-url "/transcribe")
                             {:multipart [{:name "file"
                                          :content (clojure.java.io/file audio-file-path)}]
                              :as :json
                              :throw-exceptions false
                              :socket-timeout 10000
                              :connection-timeout 5000})]
      (if (= 200 (:status response))
        (let [result (:body response)]
          (println "[NeMo] Transcription result:" result)
          result)
        {:success false
         :error (str "Server returned status " (:status response))}))
    (catch Exception e
      (println "[NeMo] Transcription error:" (.getMessage e))
      {:success false :error (str "HTTP request failed: " (.getMessage e))})))

(defn stop-nemo-server []
  "Stop is not needed - NeMo runs in Docker container"
  (println "NeMo server runs in Docker. Use 'docker-compose down' to stop.")
  true)

(defn is-running? []
  "Check if NeMo server is running"
  (check-health))
