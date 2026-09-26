            logger.info("AI Provider initializing...")
            ai_coding_provider = None
            ai_vision_provider = None
            
            mode = getattr(self.config, 'activation_mode', 'basic')
            
            # Backwards compatibility check
            if getattr(self.config, 'use_ollama', False) and mode == 'basic':
                mode = 'local'
                
            if mode == 'premium':
                logger.info(f"Using Premium AI Provider with model: {self.config.premium_model}")
                self.ai_provider = OpenRouterProvider(
                    api_key=self.config.premium_api_key,
                    model=self.config.premium_model,
                    base_url=self.config.openrouter_base_url
                )
                ai_coding_provider = self.ai_provider
                ai_vision_provider = self.ai_provider
                
            elif mode == 'local':
                logger.info(f"Using local Ollama chat model: {self.config.ollama_model}")
                self.ai_provider = OpenRouterProvider(
                    api_key="ollama_local", # Dummy key
                    model=self.config.ollama_model,
                    base_url="http://localhost:11434/v1"
                )
                
                coding_model = getattr(self.config, 'ollama_coding_model', '') or self.config.ollama_model
                logger.info(f"Using local Ollama coding model: {coding_model}")
                ai_coding_provider = OpenRouterProvider(
                    api_key="ollama_local",
                    model=coding_model,
                    base_url="http://localhost:11434/v1"
                )
                
                vision_model = getattr(self.config, 'ollama_vision_model', '')
                if vision_model:
                    logger.info(f"Using local Ollama vision model: {vision_model}")
                    ai_vision_provider = OpenRouterProvider(
                        api_key="ollama_local",
                        model=vision_model,
                        base_url="http://localhost:11434/v1"
                    )
                else:
                    logger.info("No vision model selected. Using OCR text-only mode.")
                    ai_vision_provider = None
                    
            else: # basic
                logger.info(f"Using Basic OpenRouter provider with model: {self.config.openrouter_model}")
                self.ai_provider = OpenRouterProvider(
                    api_key=self.config.openrouter_api_key,
                    model=self.config.openrouter_model,
                    base_url=self.config.openrouter_base_url
                )
                ai_coding_provider = self.ai_provider
                ai_vision_provider = self.ai_provider
