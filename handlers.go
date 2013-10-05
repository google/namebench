package handlers

import (
	"net/http"
	"history"
)

// Start handles the /start URL
func StartHandler(w http.ResponseWriter, r *http.Request) {
	fmt.Fprintf(w, "Started.")
}
