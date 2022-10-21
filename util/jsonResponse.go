package util

import (
	json "github.com/json-iterator/go"
	"namebench/model/_util/pageInfo"
	"namebench/util/apiError"
	"net/http"
)

type Response struct {
	Code       int                `json:"code"`
	Message    string             `json:"message,omitempty"`
	Success    bool               `json:"success"`
	Data       *interface{}       `json:"data,omitempty"`
	PagingInfo *pageInfo.Response `json:"paging_info,omitempty"`
}

type SResponse struct {
	Code    int         `json:"code"`
	Message string      `json:"message,omitempty"`
	Data    interface{} `json:"data"`
}

type MResponse struct {
	Code    int    `json:"code"`
	Success bool   `json:"success"`
	Message string `json:"message,omitempty"`
}

type DResponse struct {
	Code    int         `json:"code"`
	Success bool        `json:"success"`
	Data    interface{} `json:"data"`
}

func SendJSONResponse(w http.ResponseWriter, body interface{}) *apiError.Error {
	w.Header().Set("Content-Type", "application/json")
	err := json.NewEncoder(w).Encode(body)
	if err != nil {
		return apiError.InternalServerError(err)
	}

	return nil
}

func SendSuccessResponse(w http.ResponseWriter, isCreate bool) *apiError.Error {
	// HTTP Status == 201
	if isCreate {
		return SendDataResponse(w, nil, nil, http.StatusCreated)
	}

	// HTTP Status == 200
	return SendDataResponse(w, nil, nil, http.StatusOK)

}

func SendDataResponse(w http.ResponseWriter, data interface{}, pi *pageInfo.Response, code int) *apiError.Error {
	resp := Response{Code: code, Message: "", Success: code >= 200 && code < 300, PagingInfo: pi}
	if data != nil {
		resp.Data = &data
	}
	return SendJSONResponse(w, resp)
}

func SendErrCodeResponse(w http.ResponseWriter, customCode, code int) *apiError.Error {
	w.WriteHeader(code)
	return SendJSONResponse(w, Response{Code: customCode, Success: false})
}

func SendMsgResponse(w http.ResponseWriter, msg string, code int) *apiError.Error {
	if code >= 100 && code < 600 {
		w.WriteHeader(code)
	}

	return SendJSONResponse(w, MResponse{
		Code:    code,
		Message: msg,
		Success: code >= 200 && code < 300,
	})
}

func SendNoContent(w http.ResponseWriter) *apiError.Error {
	w.WriteHeader(http.StatusNoContent)

	return nil
}
