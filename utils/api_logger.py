import json
import os
from datetime import datetime
from pathlib import Path

class APILogger:
    def __init__(self, log_dir="logs", pretty=False):
        """Initialize the logger with a directory for log files.
        
        Args:
            log_dir (str): Directory where logs will be stored
            pretty (bool): If True, logs will be stored in a pretty-printed format
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.pretty = pretty
        
        # Create log files for the current day
        date_str = datetime.now().strftime('%Y-%m-%d')
        if pretty:
            self.log_file = self.log_dir / f"api_calls_{date_str}.json"
            # Initialize the file with an empty array if it doesn't exist
            if not self.log_file.exists():
                with open(self.log_file, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
        else:
            self.log_file = self.log_dir / f"api_calls_{date_str}.jsonl"
        
    def log_api_call(self, request_data, response_data, status="success", error=None):
        """Log an API call with its request and response data."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "request": {
                "messages": request_data.get("messages", []),
                "model": request_data.get("model", "unknown"),
                "response_format": request_data.get("response_format", {})
            },
            "response": response_data,
            "status": status
        }
        
        if error:
            log_entry["error"] = str(error)
            
        if self.pretty:
            # Pour le format pretty, on doit lire tout le fichier, ajouter l'entrée et réécrire
            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                logs = []
            
            logs.append(log_entry)
            
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump(logs, ensure_ascii=False, indent=2, fp=f)
        else:
            # Format JSONL : on ajoute simplement la ligne
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
    def get_logs(self, date=None, pretty_print=None):
        """Retrieve logs for a specific date or all logs if date is None.
        
        Args:
            date (str): Optional date in format YYYY-MM-DD
            pretty_print (bool): Override instance pretty setting for this call
        """
        use_pretty = self.pretty if pretty_print is None else pretty_print
        
        if date:
            if use_pretty:
                log_file = self.log_dir / f"api_calls_{date}.json"
            else:
                log_file = self.log_dir / f"api_calls_{date}.jsonl"
            if not log_file.exists():
                return []
            files = [log_file]
        else:
            if use_pretty:
                files = sorted(self.log_dir.glob("api_calls_*.json"))
            else:
                files = sorted(self.log_dir.glob("api_calls_*.jsonl"))
            
        logs = []
        for file in files:
            if use_pretty:
                with open(file, "r", encoding="utf-8") as f:
                    try:
                        file_logs = json.load(f)
                        logs.extend(file_logs)
                    except json.JSONDecodeError:
                        continue
            else:
                with open(file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            logs.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            continue
        return logs
    
    def convert_log_format(self, date=None, to_pretty=True):
        """Convert log files between JSONL and pretty JSON formats.
        
        Args:
            date (str): Optional date in format YYYY-MM-DD to convert specific file
            to_pretty (bool): If True, converts to pretty format, otherwise to JSONL
        """
        if date:
            dates = [date]
        else:
            # Get all unique dates from both formats
            json_files = set(f.stem.replace('api_calls_', '') for f in self.log_dir.glob("api_calls_*.json"))
            jsonl_files = set(f.stem.replace('api_calls_', '') for f in self.log_dir.glob("api_calls_*.jsonl"))
            dates = sorted(json_files.union(jsonl_files))
        
        for d in dates:
            jsonl_file = self.log_dir / f"api_calls_{d}.jsonl"
            json_file = self.log_dir / f"api_calls_{d}.json"
            
            # Lire les logs existants
            logs = []
            if to_pretty and jsonl_file.exists():
                with open(jsonl_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            logs.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            continue
                # Écrire en format pretty
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(logs, f, ensure_ascii=False, indent=2)
                # Optionnel : supprimer l'ancien fichier
                jsonl_file.unlink(missing_ok=True)
                
            elif not to_pretty and json_file.exists():
                with open(json_file, "r", encoding="utf-8") as f:
                    try:
                        logs = json.load(f)
                    except json.JSONDecodeError:
                        continue
                # Écrire en format JSONL
                with open(jsonl_file, "w", encoding="utf-8") as f:
                    for entry in logs:
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                # Optionnel : supprimer l'ancien fichier
                json_file.unlink(missing_ok=True) 