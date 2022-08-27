package apiError

import (
	"fmt"
	"github.com/pkg/errors"
	"net/http"
	"strings"
)

const (
	UnknownServerError = 5000
)

// Error error returned by APIHandler
type Error struct {
	Error   error
	Message string
	Code    int
}

func New(message string, code int) *Error {
	return &Error{nil, message, code}
}

func DetectError(err error) *Error {
	errStr := strings.ToLower(err.Error())
	if strings.Contains(errStr, "invalid") {
		return &Error{nil, errStr, http.StatusBadRequest}
	} else if strings.Contains(errStr, "author") {
		return NotAuthorizedError(errStr)
	} else if strings.Contains(errStr, "found") {
		return NotFoundError(errStr)
	} else if strings.Contains(errStr, "legal") {
		return UnavailableLegalReason(errStr)
	}

	return InternalServerError(err)
}

func InternalServerErrorLoc(loc string, err error) *Error {
	return &Error{errors.New(fmt.Sprintf("%s: %s", loc, err)), "Unknown error! Try again", UnknownServerError}
}

func InternalServerError(err error) *Error {
	return &Error{err, "Unknown error! Try again", UnknownServerError}
}

func BadRequestError(location string) *Error {
	return &Error{nil, fmt.Sprintf("'%s' is invalid or missing", location), http.StatusBadRequest}
}

func BadRequestMsgErr(msg string) *Error {
	return &Error{nil, msg, http.StatusBadRequest}
}

func NotAuthorizedError(message string) *Error {
	return &Error{nil, message, http.StatusUnauthorized}
}
func NotAuthorizedUser() *Error {
	return NotFoundError("unauthorized")
}

func SomethingMissingError(message string) *Error {
	return &Error{nil, message, http.StatusBadRequest}
}

func NotFoundError(message string) *Error {
	return &Error{nil, message, http.StatusNotFound}
}

func UnavailableLegalReason(message string) *Error {
	return &Error{nil, message, http.StatusUnavailableForLegalReasons}
}

func ConflictError(message string) *Error {
	return &Error{nil, message, http.StatusConflict}
}
