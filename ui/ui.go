// The ui package contains methods for handling UI URL's.
package ui

import (
	"fmt"
	"github.com/google/namebench/history"
	"net/http"
)

func RegisterHandlers() {
	http.HandleFunc("/", Index)
	http.HandleFunc("/submit", Submit)
}

// Index handles /
func Index(w http.ResponseWriter, r *http.Request) {
	records, err := history.Chrome(30, 3000)
	fmt.Fprintf(w, fmt.Sprintf("%s: %s", err, history.ExternalHostnames(records)))
	return
}

// Submit handles /submit
func Submit(w http.ResponseWriter, r *http.Request) {
	entries, err := history.Chrome(30, 5)
	if err != nil {
		fmt.Fprintf(w, fmt.Sprintf("ERROR: %s", err))
		return
	}
	fmt.Fprintf(w, fmt.Sprintf("%s", entries))
	return
}
