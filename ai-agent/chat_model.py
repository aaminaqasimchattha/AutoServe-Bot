import os
import numpy as np
import logging
from pathlib import Path
import string
import pickle

try:
    import tensorflow as tf
    from tensorflow import keras
except ImportError:
    import keras

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to the model
MODEL_PATH = os.path.join(os.path.dirname(__file__), "seq2seq_model.keras")

class ChatModel:
    def __init__(self, model_path=MODEL_PATH):
        """Initialize the chat model"""
        self.model = None
        self.model_path = model_path
        self.max_encoder_seq_length = 20
        self.max_decoder_seq_length = 20
        self.vocabulary = None
        self.reverse_vocabulary = None
        self.load_model()
        self._create_vocabulary()
        
    def load_model(self):
        """Load the seq2seq model"""
        try:
            if not os.path.exists(self.model_path):
                logger.error(f"❌ Model not found at {self.model_path}")
                return False
                
            self.model = keras.models.load_model(self.model_path)
            logger.info(f"✅ Model loaded successfully from {self.model_path}")
            
            # Log model info
            if self.model is not None and hasattr(self.model, 'layers') and isinstance(self.model, keras.Model):
                logger.info(f"📊 Model has {len(self.model.layers)} layers")
            
            # Try to get input/output shapes
            if self.model is not None and hasattr(self.model, 'input_shape') and isinstance(self.model, keras.Model):
                try:
                    logger.info(f"   Input shape: {self.model.input_shape}")
                except Exception:
                    pass
            if self.model is not None and hasattr(self.model, 'output_shape') and isinstance(self.model, keras.Model):
                try:
                    logger.info(f"   Output shape: {self.model.output_shape}")
                except Exception:
                    pass
            
            return True
        except Exception as e:
            logger.error(f"❌ Error loading model: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _create_vocabulary(self):
        """Create character-level vocabulary"""
        # Create a simple character vocabulary
        chars = set(string.ascii_lowercase + string.digits + string.punctuation + ' ')
        self.vocabulary = {char: idx + 1 for idx, char in enumerate(sorted(chars))}
        self.vocabulary['<PAD>'] = 0
        self.reverse_vocabulary = {idx: char for char, idx in self.vocabulary.items()}
        logger.info(f"✅ Vocabulary created with {len(self.vocabulary)} characters")
    
    def preprocess_input(self, text):
        """
        Preprocess the input text for the model
        """
        try:
            # Convert to lowercase
            text = text.lower().strip()
            
            # Remove extra whitespace
            text = ' '.join(text.split())
            
            # Keep only characters that are in our vocabulary
            text = ''.join([char if char in self.vocabulary else ' ' for char in text])
            
            # Pad/truncate to expected length
            if len(text) > self.max_encoder_seq_length:
                text = text[:self.max_encoder_seq_length]
            
            logger.info(f"📝 Processed input: {text}")
            return text
        except Exception as e:
            logger.error(f"Error preprocessing input: {e}")
            return text
    
    def _text_to_sequence(self, text):
        """Convert text to sequence of integers"""
        try:
            sequence = [self.vocabulary.get(char, 0) for char in text]
            # Pad sequence
            if len(sequence) < self.max_encoder_seq_length:
                sequence = sequence + [0] * (self.max_encoder_seq_length - len(sequence))
            return sequence[:self.max_encoder_seq_length]
        except Exception as e:
            logger.error(f"Error converting text to sequence: {e}")
            return [0] * self.max_encoder_seq_length
    
    def _sequence_to_text(self, sequence):
        """Convert sequence of integers back to text"""
        try:
            text = ''
            for idx in sequence:
                if idx == 0:  # PAD token
                    continue
                char = self.reverse_vocabulary.get(idx, '')
                if char and char != '<PAD>':
                    text += char
            return text.strip()
        except Exception as e:
            logger.error(f"Error converting sequence to text: {e}")
            return "Error decoding response"
    
    def generate_response(self, user_input):
        """
        Generate a response from the seq2seq model based on user input.
        """
        try:
            if self.model is None:
                logger.error("Model not loaded")
                return "I'm sorry, the model is not available. Please try again later."
            
            logger.info(f"🤖 Generating response for: '{user_input}'")
            
            # Preprocess the input
            processed_input = self.preprocess_input(user_input)
            
            # Convert text to sequence
            input_sequence = self._text_to_sequence(processed_input)
            logger.info(f"📊 Input sequence length: {len(input_sequence)}")
            
            # Prepare input for the model
            try:
                # Create batch (add batch dimension)
                input_batch = np.array([input_sequence])
                logger.info(f"📥 Input shape for model: {input_batch.shape}")
                
                # Make prediction
                prediction = self.model.predict(input_batch, verbose=0)
                logger.info(f"📤 Prediction shape: {prediction.shape}")
                
                # Process the output - convert to readable text
                response = self._decode_prediction(prediction)
                
                logger.info(f"✅ Generated response: {response}")
                return response if response.strip() else "I'm processing your request. Could you please rephrase?"
                
            except Exception as e:
                logger.warning(f"⚠️ Prediction error: {e}")
                import traceback
                traceback.print_exc()
                return f"I understand you asked about: '{user_input}'. Let me help you with that."
        
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            import traceback
            traceback.print_exc()
            return "Sorry, I encountered an error processing your message."
    
    def _decode_prediction(self, prediction):
        """
        Decode the model's prediction output into readable text.
        Handles various output formats from seq2seq models.
        """
        try:
            if isinstance(prediction, np.ndarray):
                logger.info(f"Prediction type: {type(prediction)}, dtype: {prediction.dtype}, shape: {prediction.shape}")
                
                # Remove batch dimension if present
                if prediction.ndim > 1 and prediction.shape[0] == 1:
                    prediction = prediction[0]
                
                # If it's 2D (sequence_length, vocab_size) - probabilities
                if prediction.ndim == 2:
                    # Apply argmax to get most likely token at each position
                    predicted_ids = np.argmax(prediction, axis=-1)
                    logger.info(f"Predicted IDs: {predicted_ids}")
                    response = self._sequence_to_text(predicted_ids)
                    return response
                
                # If it's 1D - could be token IDs or confidence scores
                elif prediction.ndim == 1:
                    if prediction.max() > 1 or prediction.dtype in [np.int32, np.int64]:
                        # Looks like token IDs
                        response = self._sequence_to_text(prediction)
                    else:
                        # Looks like probabilities - not expected for output
                        predicted_ids = np.argmax(prediction)
                        response = self._sequence_to_text([predicted_ids])
                    return response
                
                else:
                    logger.warning(f"Unexpected prediction shape: {prediction.shape}")
                    return "I'm processing your message..."
            
            return str(prediction)
        except Exception as e:
            logger.error(f"Error decoding prediction: {e}")
            import traceback
            traceback.print_exc()
            return "I'm having trouble understanding. Could you rephrase?"



# Initialize the model globally
chat_model = None

def initialize_model():
    """Initialize the chat model on startup"""
    global chat_model
    try:
        chat_model = ChatModel()
        logger.info("✅ Chat model initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize chat model: {e}")
        return False

def get_chat_response(user_message):
    """
    Get a response from the chat model.
    Call this from your webhook handler.
    """
    global chat_model
    
    if chat_model is None:
        logger.warning("Chat model not initialized, initializing now...")
        initialize_model()
    
    if chat_model is None:
        return "I'm sorry, I'm not available right now. Please try again later."
    
    return chat_model.generate_response(user_message)


if __name__ == "__main__":
    # Test the model
    if initialize_model():
        test_message = "Hello, how are you?"
        response = get_chat_response(test_message)
        print(f"User: {test_message}")
        print(f"Bot: {response}")
