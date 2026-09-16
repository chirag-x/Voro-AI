    def cycle_activation_mode(self):
        modes = ['premium', 'basic', 'local']
        current = getattr(self.config, 'activation_mode', 'basic')
        try:
            idx = modes.index(current)
        except ValueError:
            idx = 1
            
        next_mode = modes[(idx + 1) % len(modes)]
        self.config.activation_mode = next_mode
        
        import os
        from dotenv import set_key
        env_path = os.path.join(os.getcwd(), ".env")
        set_key(env_path, "ACTIVATION_MODE", next_mode)
        
        self.reload_ai_provider()
        
        # Trigger UI update if callback exists
        if hasattr(self, 'on_activation_switched_callback') and self.on_activation_switched_callback:
            self.on_activation_switched_callback(next_mode)

    def reload_ai_provider(self):
        logger.info("AI Provider initializing...")
        ai_coding_provider = None
        ai_vision_provider = None
        
        mode = getattr(self.config, 'activation_mode', 'basic')
        
        # Backwards compatibility check
        if getattr(self.config, 'use_ollama', False) and mode == 'basic':
            mode = 'local'
            
        from app.ai.openrouter import OpenRouterProvider
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
            
        from app.answer.engine import AnswerEngine
        self.answer_engine = AnswerEngine(
            ai_provider=self.ai_provider,
            context_manager=self.context_manager,
            mm_engine=self.mm_engine,
            max_context_turns=self.config.conversation_history_depth * 2,
            ai_coding_provider=ai_coding_provider,
            ai_vision_provider=ai_vision_provider
        )
