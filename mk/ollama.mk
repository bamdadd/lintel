ollama-pull: ## Pull Ollama models (qwen2.5-coder:32b, llama3.1:70b)
	ollama pull qwen2.5-coder:32b
	ollama pull llama3.1:70b

ollama-serve: ollama-pull ## Pull models and start Ollama server
	ollama serve
