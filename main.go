package main

import (
	"flag"
	"fmt"
	"log"
	"namebench/ui"
	"namebench/util/logger"
	"net"
	"net/http"
	"os"
	"os/exec"
)

var nwPath = flag.String("nw_path", "/Applications/nwjs.app/Contents/MacOS/nwjs",
	"Path to nodejs-webkit binary")
var nwPackage = flag.String("nw_package", "./ui/nw/app.nw", "Path to nw.js package")
var port = flag.Int("port", 0, "Port to listen on")
var mode = flag.String("mode", "", "Use for testing immediately, put '-mode now' or '--mode now'")

func init() {
	logger.Init()
}

// openWindow opens a nodejs-webkit window, and points it at the given URL.
func openWindow(url string) error {
	os.Setenv("APP_URL", url)
	cmd := exec.Command(*nwPath, *nwPackage)
	if err := cmd.Run(); err != nil {
		logger.L.Errorf("error running %s %s: %s", *nwPath, *nwPackage, err)
		return err
	}
	return nil
}

func main() {
	flag.Parse()
	ui.RegisterHandlers()

	if *mode == "now" {
		result := ui.DoDnsSec()
		fmt.Println(result.String())
		return
	}

	if *port != 0 {
		logger.L.Infof("Listening at :%d", *port)
		err := http.ListenAndServe(fmt.Sprintf(":%d", *port), nil)
		if err != nil {
			logger.L.Fatalf("Failed to listen on %d: %s", *port, err)
		}
	} else {
		listener, err := net.Listen("tcp4", "127.0.0.1:0")
		if err != nil {
			log.Fatalf("Failed to listen: %s", err)
		}
		url := fmt.Sprintf("http://%s/", listener.Addr().String())
		logger.L.Infof("URL: %s", url)
		go openWindow(url)
		logger.L.Fatal(http.Serve(listener, nil))
	}
}
