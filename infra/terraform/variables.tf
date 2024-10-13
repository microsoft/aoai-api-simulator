variable "azure_subscription_id" {
  description = "The Azure subscription ID"
  type        = string
  
}

variable "resource_group_name" {
  description = "The name of the resource group to create"
  type        = string
}

variable "location" {
  description = "The location of the resource group to create"
  type        = string
}

variable "base_name" {
  description = "The base name for resources"
  type        = string
  
}

variable simulator_image_tag {
  description = "The tag for the simulator image"
  type        = string
}

variable "simulator_mode" {
  description = "The mode for the simulator"
  type        = string
}

variable "simulator_api_key" {
  description = "The API key for the simulator"
  type        = string
}

variable "recording_dir" {
  description = "The directory for recordings"
  type        = string
}

variable "recording_auto_save" {
  description = "The directory for auto saving recordings"
  type        = string
}

variable "extension_path" {
  description = "The path to the extension"
  type        = string
}

variable "azure_openai_endpoint" {
  description = "The endpoint for the OpenAI service"
  type        = string
}

variable "azure_openai_key" {
  description = "The key for the OpenAI service"
  type        = string
}

variable "log_level" {
  description = "The log level for the simulator"
  type        = string
}

variable "current_user_principal_id" {
  description = "The current user principal ID"
  type        = string
}