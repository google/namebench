package main

import (
	"flag"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
)

var nw_path = flag.String("nw_path", "/Applications/node-webkit.app/Contents/MacOS/node-webkit",
	"Path to nodejs-webkit binary")
var nw_package = flag.String("nw_package", "../ui/app.nw", "Path to nodejs-webkit package")

// openWindow opens a nodejs-webkit window, and points it at the given URL.
func openWindow(url string) (err error) {
	os.Setenv("APP_URL", url)
	cmd := exec.Command(*nw_path, *nw_package)
	if err := cmd.Run(); err != nil {
		log.Printf("error running %s %s: %s", *nw_path, *nw_package, err)
		return err
	}
	return
}

func main() {
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		log.Fatalf("Failed to listen: %s", err)
	}
	url := fmt.Sprintf("http://%s/start", listener.Addr().String())
	log.Printf("URL: %s", url)
	go openWindow(url)
	http.HandleFunc("/start", handlers.Start)
	panic(http.Serve(listener, nil))
}
