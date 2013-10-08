// The ui package contains methods for handling UI URL's.
package ui

import (
	"fmt"
	"github.com/google/namebench/dnsqueue"
	"github.com/google/namebench/history"
	"log"
	"net/http"
)

const (
	// How many requests/responses can be queued at once
	QUEUE_LENGTH = 65535

	// Number of workers (same as Chrome's DNS prefetch queue)
	WORKERS = 8
)

func RegisterHandlers() {
	http.HandleFunc("/", Index)
	http.HandleFunc("/submit", Submit)
}

// Index handles /
func Index(w http.ResponseWriter, r *http.Request) {
	records, err := history.Chrome(30)
	if err != nil {
		panic(err)
	}

	q := dnsqueue.StartQueue(QUEUE_LENGTH, WORKERS)
	hostnames := history.Random(16, history.Uniq(history.ExternalHostnames(records)))

	for _, record := range hostnames {
		q.Add("8.8.8.8:53", "A", record+".")
		log.Printf("Added %s", record)
	}
	log.Printf("Sending comp")
	q.SendCompletionSignal()
	log.Printf("comp sent")
	answered := 0

	for {
		if answered == len(hostnames) {
			break
		}
		result := <-q.Results
		answered += 1
		fmt.Fprintf(w, "%s of %s responses complete: %s", answered, len(hostnames), result)
	}
	return
}

// Submit handles /submit
func Submit(w http.ResponseWriter, r *http.Request) {
	return
}
