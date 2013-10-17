// The ui package contains methods for handling UI URL's.
package ui

import (
	"html/template"
	"log"
	"net/http"
	"strings"

	"github.com/google/namebench/dnschecks"
	"github.com/google/namebench/dnsqueue"
	"github.com/google/namebench/history"
)

const (
	// How many requests/responses can be queued at once
	QUEUE_LENGTH = 65535

	// Number of workers (same as Chrome's DNS prefetch queue)
	WORKERS = 8

	// Number of tests to run
	COUNT = 50

	// How far back to reach into browser history
	HISTORY_DAYS = 30
)

var (
	indexTmpl = loadTemplate("ui/templates/index.html")
)

// RegisterHandler registers all known handlers.
func RegisterHandlers() {
	http.HandleFunc("/", Index)
	http.Handle("/static/", http.StripPrefix("/static", http.FileServer(http.Dir("ui/static"))))
	http.HandleFunc("/submit", Submit)
	http.HandleFunc("/dnssec", DnsSec)
}

// loadTemplate loads a set of templates.
func loadTemplate(paths ...string) *template.Template {
	t := template.New(strings.Join(paths, ","))
	_, err := t.ParseFiles(paths...)
	if err != nil {
		panic(err)
	}
	return t
}

// Index handles /
func Index(w http.ResponseWriter, r *http.Request) {
	if err := indexTmpl.ExecuteTemplate(w, "index.html", nil); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
	return
}

// DnsSec handles /dnssec
func DnsSec(w http.ResponseWriter, r *http.Request) {
	servers := []string{
		"8.8.8.8:53",
		"75.75.75.75:53",
		"4.2.2.1:53",
		"208.67.222.222:53",
	}
	for _, ip := range servers {
		result, err := dnschecks.DnsSec(ip)
		log.Printf("%s DNSSEC: %s (%s)", ip, result, err)
	}
}

// Submit handles /submit
func Submit(w http.ResponseWriter, r *http.Request) {
	records, err := history.Chrome(HISTORY_DAYS)
	if err != nil {
		panic(err)
	}

	q := dnsqueue.StartQueue(QUEUE_LENGTH, WORKERS)
	hostnames := history.Random(COUNT, history.Uniq(history.ExternalHostnames(records)))

	for _, record := range hostnames {
		q.Add("8.8.8.8:53", "A", record+".")
		log.Printf("Added %s", record)
	}
	q.SendCompletionSignal()
	answered := 0
	for {
		if answered == len(hostnames) {
			break
		}
		result := <-q.Results
		answered += 1
		log.Printf("%s", result)
	}
	return
}
