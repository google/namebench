package util

import (
	"fmt"
	json "github.com/json-iterator/go"
	"namebench/model/_util/pageInfo"
	"namebench/util/apiError"
	"namebench/util/logger"
	"net/http"
	"strings"
)

type errorResp struct {
	Message string
	Success bool `json:"success"`
	Code    int  `json:"code"`
}

func JSONHandler(w http.ResponseWriter, r *http.Request, data interface{}, pi *pageInfo.Response, code int) {
	if err := SendDataResponse(w, data, pi, code); err != nil {
		ErrorHandler(w, r, err)
		return
	}
}

// ErrorHandler returns a httprouter handler
func ErrorHandler(w http.ResponseWriter, r *http.Request, err *apiError.Error) {
	if err != nil {
		errMsg := fmt.Sprintf("%s : %s : %s", r.RequestURI, err.Error, err.Message)
		if err.Code >= 500 && err.Code < 600 {
			logger.L.Error(errMsg)
		} else if err.Code >= 400 && err.Code < 500 {
			logger.L.Warn(errMsg)
		}

		param := &errorResp{"", false, err.Code}
		if err.Code != apiError.UnknownServerError {
			param.Message = err.Message
		}

		w.Header().Set("Content-Type", "application/json")
		if strings.Contains(strings.ToLower(err.Message), "invalid") {
			w.WriteHeader(http.StatusBadRequest)
		} else if err.Code >= 400 && err.Code < 600 {
			w.WriteHeader(err.Code)
		} else {
			w.WriteHeader(http.StatusInternalServerError)
		}
		_ = json.NewEncoder(w).Encode(param)
	}
}
